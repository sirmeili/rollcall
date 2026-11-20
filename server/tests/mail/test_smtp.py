"""The SMTP sender against a small fake SMTP server on a local socket: starttls, tls and
none, with and without a login."""

import ssl
from collections.abc import Callable
from email import message_from_bytes, policy
from pathlib import Path

import pytest
from fake_smtp import HOST, FakeSmtp, RunningSmtp, closed_port, make_certificate
from pydantic import SecretStr

from filament_tracker.mail.message import Email, mime_message
from filament_tracker.mail.smtp import (
    NO_STARTTLS,
    REFUSED_LOGIN,
    TLS_FAILED,
    UNREACHABLE,
    SmtpSender,
)
from filament_tracker.mail.transport import MailError, Security, SmtpServer

PASSWORD = "smtp-password-value-1234"  # noqa: S105 - test value
FROM = "RollCall <rollcall@example.com>"
EMAIL = Email(
    to="sam@example.com",
    subject="RollCall test email",
    text="This is a test email from RollCall.\n",
    html="<p>This is a test email from RollCall.</p>",
)


@pytest.fixture(scope="module")
def certificate(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    return make_certificate(tmp_path_factory.mktemp("smtp-cert"))


@pytest.fixture
def server_tls(certificate: tuple[Path, Path]) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(*certificate)
    return context


@pytest.fixture
def trusting(certificate: tuple[Path, Path]) -> Callable[[], ssl.SSLContext]:
    """A client context that trusts the test certificate, as the system's would a real one."""
    return lambda: ssl.create_default_context(cafile=str(certificate[0]))


def smtp(port: int, security: Security, user: str | None = None, password: str = PASSWORD):  # noqa: ANN201
    return SmtpServer(HOST, port, security, user, SecretStr(password) if user else None, FROM)


@pytest.mark.parametrize(
    ("security", "implicit_tls", "encrypted"),
    [("starttls", False, True), ("tls", True, True), ("none", False, False)],
)
def test_sends_with_each_security_and_a_login(
    server_tls: ssl.SSLContext,
    trusting: Callable[[], ssl.SSLContext],
    security: Security,
    implicit_tls: bool,
    encrypted: bool,
) -> None:
    fake = FakeSmtp(server_tls, implicit_tls=implicit_tls, accounts={"rollcall": PASSWORD})
    with RunningSmtp(fake) as running:
        SmtpSender(context=trusting).send(
            smtp(running.port, security, "rollcall"), mime_message(EMAIL, FROM)
        )

    [received] = fake.received
    assert received.encrypted is encrypted
    assert received.login == ("rollcall", PASSWORD)
    assert received.mail_from == "rollcall@example.com"
    assert received.rcpt_to == ["sam@example.com"]
    message = message_from_bytes(received.data, policy=policy.default)
    assert message["Subject"] == "RollCall test email"
    assert message.get_body(("plain",)).get_content().strip() == EMAIL.text.strip()
    assert message.get_body(("html",)).get_content().strip() == EMAIL.html


def test_sends_without_a_login_when_no_user_is_set(
    server_tls: ssl.SSLContext, trusting: Callable[[], ssl.SSLContext]
) -> None:
    fake = FakeSmtp(server_tls)
    with RunningSmtp(fake) as running:
        SmtpSender(context=trusting).send(smtp(running.port, "starttls"), mime_message(EMAIL, FROM))

    [received] = fake.received
    assert received.login is None


def test_a_wrong_password_is_refused_without_repeating_it(
    server_tls: ssl.SSLContext, trusting: Callable[[], ssl.SSLContext]
) -> None:
    fake = FakeSmtp(server_tls, accounts={"rollcall": "the real one"})
    with RunningSmtp(fake) as running, pytest.raises(MailError) as raised:
        SmtpSender(context=trusting).send(
            smtp(running.port, "starttls", "rollcall"), mime_message(EMAIL, FROM)
        )

    assert str(raised.value) == REFUSED_LOGIN
    assert PASSWORD not in str(raised.value)
    assert fake.received == []


def test_starttls_is_required_when_chosen(
    server_tls: ssl.SSLContext, trusting: Callable[[], ssl.SSLContext]
) -> None:
    fake = FakeSmtp(server_tls, offer_starttls=False, accounts={"rollcall": PASSWORD})
    with RunningSmtp(fake) as running, pytest.raises(MailError) as raised:
        SmtpSender(context=trusting).send(
            smtp(running.port, "starttls", "rollcall"), mime_message(EMAIL, FROM)
        )

    assert str(raised.value) == NO_STARTTLS
    assert fake.received == []


def test_an_untrusted_certificate_is_refused(server_tls: ssl.SSLContext) -> None:
    fake = FakeSmtp(server_tls, implicit_tls=True)
    with RunningSmtp(fake) as running, pytest.raises(MailError) as raised:
        SmtpSender().send(smtp(running.port, "tls"), mime_message(EMAIL, FROM))

    assert str(raised.value) == TLS_FAILED


def test_a_server_that_is_not_there_is_unreachable() -> None:
    with pytest.raises(MailError) as raised:
        SmtpSender(timeout=10).send(smtp(closed_port(), "none"), mime_message(EMAIL, FROM))

    assert str(raised.value) == UNREACHABLE
