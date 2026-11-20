"""A small SMTP server on a local socket, for testing the SMTP sender. It speaks just
enough SMTP: EHLO, STARTTLS, AUTH PLAIN and LOGIN, MAIL, RCPT, DATA and QUIT, and records
what it was sent. The test certificate is made when the tests run, never stored."""

import base64
import datetime
import socket
import socketserver
import ssl
import threading
from dataclasses import dataclass, field
from ipaddress import IPv4Address
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

HOST = "127.0.0.1"


def make_certificate(directory: Path) -> tuple[Path, Path]:
    """A throwaway self-signed certificate for 127.0.0.1 and localhost."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(IPv4Address(HOST))]
            ),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = directory / "smtp.pem", directory / "smtp.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


@dataclass
class Received:
    mail_from: str
    rcpt_to: list[str]
    data: bytes
    login: tuple[str, str] | None
    encrypted: bool


@dataclass
class FakeSmtp:
    """Settings for the server, and what it received."""

    tls_context: ssl.SSLContext | None
    implicit_tls: bool = False
    offer_starttls: bool = True
    accounts: dict[str, str] = field(default_factory=dict)
    received: list[Received] = field(default_factory=list)


class _Handler(socketserver.StreamRequestHandler):
    server: "_Server"

    def setup(self) -> None:
        fake = self.server.fake
        self.encrypted = False
        if fake.implicit_tls:
            assert fake.tls_context is not None
            self.request = fake.tls_context.wrap_socket(self.request, server_side=True)
            self.encrypted = True
        super().setup()

    def _reply(self, line: str) -> None:
        self.wfile.write(line.encode() + b"\r\n")
        self.wfile.flush()

    def _read(self) -> str:
        return self.rfile.readline().decode().rstrip("\r\n")

    def handle(self) -> None:  # noqa: C901 - one small SMTP state machine
        fake = self.server.fake
        login: tuple[str, str] | None = None
        mail_from, rcpt_to = "", []
        self._reply("220 fake ESMTP")
        while line := self._read():
            verb = line.split(" ", 1)[0].upper()
            if verb in ("EHLO", "HELO"):
                lines = ["250-fake"]
                if fake.offer_starttls and not self.encrypted and fake.tls_context:
                    lines.append("250-STARTTLS")
                if fake.accounts:
                    lines.append("250-AUTH PLAIN LOGIN")
                lines.append("250 SMTPUTF8")
                for reply in lines:
                    self._reply(reply)
            elif verb == "STARTTLS":
                self._reply("220 go ahead")
                assert fake.tls_context is not None
                self.connection = fake.tls_context.wrap_socket(self.connection, server_side=True)
                self.request = self.connection
                self.rfile = self.connection.makefile("rb")
                self.wfile = self.connection.makefile("wb")
                self.encrypted = True
            elif verb == "AUTH":
                login = self._auth(line)
                if login is None:
                    self._reply("535 authentication failed")
                else:
                    self._reply("235 ok")
            elif verb == "MAIL":
                mail_from, rcpt_to = line.split(":", 1)[1].split()[0].strip("<>"), []
                self._reply("250 ok")
            elif verb == "RCPT":
                rcpt_to.append(line.split(":", 1)[1].strip().strip("<>"))
                self._reply("250 ok")
            elif verb == "DATA":
                self._reply("354 go ahead")
                data = b""
                while (chunk := self.rfile.readline()) not in (b".\r\n", b""):
                    data += chunk
                fake.received.append(Received(mail_from, rcpt_to, data, login, self.encrypted))
                self._reply("250 queued")
            elif verb == "QUIT":
                self._reply("221 bye")
                return
            else:
                self._reply("250 ok")

    def _auth(self, line: str) -> tuple[str, str] | None:
        parts = line.split()
        if parts[1].upper() == "PLAIN":
            if len(parts) > 2:
                encoded = parts[2]
            else:
                self._reply("334 ")
                encoded = self._read()
            _, user, password = base64.b64decode(encoded).decode().split("\0")
        else:
            self._reply("334 VXNlcm5hbWU6")
            user = base64.b64decode(self._read()).decode()
            self._reply("334 UGFzc3dvcmQ6")
            password = base64.b64decode(self._read()).decode()
        accounts = self.server.fake.accounts
        return (user, password) if accounts.get(user) == password else None


class _Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, fake: FakeSmtp) -> None:
        super().__init__((HOST, 0), _Handler)
        self.fake = fake


class RunningSmtp:
    def __init__(self, fake: FakeSmtp) -> None:
        self.fake = fake
        self._server = _Server(fake)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "RunningSmtp":
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._server.shutdown()
        self._server.server_close()


def closed_port() -> int:
    """A local port nothing listens on."""
    with socket.socket() as probe:
        probe.bind((HOST, 0))
        return probe.getsockname()[1]
