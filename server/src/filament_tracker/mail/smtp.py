"""The SMTP sender, the default mail transport (standard library only).

`starttls` connects in plain text and upgrades before logging in, `tls` connects over TLS
from the start (usually port 465), and `none` never encrypts. Certificates are checked
against the system's trusted ones. Errors become a short safe message: never the
password, and never the mail server's own text.
"""

import smtplib
import ssl
from collections.abc import Callable
from email.message import EmailMessage

from filament_tracker.mail.transport import MailError, SmtpServer

TIMEOUT_SECONDS = 15.0

REFUSED_LOGIN = "The mail server refused the user name or password."
UNREACHABLE = "Can't reach the mail server. Check the host and port."
TIMED_OUT = "The mail server didn't answer in time."
NO_STARTTLS = "The mail server doesn't offer STARTTLS. Try tls or none."
NO_LOGIN = "The mail server doesn't accept a login on this connection."
TLS_FAILED = "Couldn't make a secure connection to the mail server."
REFUSED_FROM = "The mail server refused the from address."
REFUSED_TO = "The mail server refused the recipient's address."
DISCONNECTED = "The mail server closed the connection."


class SmtpSender:
    def __init__(
        self,
        *,
        context: Callable[[], ssl.SSLContext] = ssl.create_default_context,
        timeout: float = TIMEOUT_SECONDS,
    ) -> None:
        self._context = context
        self._timeout = timeout

    def send(self, server: SmtpServer, message: EmailMessage) -> None:
        step = "connect"
        try:
            with self._connect(server) as smtp:
                if server.security == "starttls":
                    step = "starttls"
                    smtp.starttls(context=self._context())
                if server.user:
                    step = "login"
                    password = server.password.get_secret_value() if server.password else ""
                    smtp.login(server.user, password)
                step = "send"
                smtp.send_message(message)
        except smtplib.SMTPAuthenticationError:
            raise MailError(REFUSED_LOGIN) from None
        except smtplib.SMTPNotSupportedError:
            raise MailError(NO_STARTTLS if step == "starttls" else NO_LOGIN) from None
        except smtplib.SMTPSenderRefused:
            raise MailError(REFUSED_FROM) from None
        except smtplib.SMTPRecipientsRefused:
            raise MailError(REFUSED_TO) from None
        except smtplib.SMTPServerDisconnected:
            raise MailError(DISCONNECTED) from None
        except smtplib.SMTPResponseException as error:
            raise MailError(
                f"The mail server answered with an error ({error.smtp_code})."
            ) from None
        except smtplib.SMTPException:
            raise MailError("The mail server answered with an error.") from None
        except ssl.SSLError:
            raise MailError(TLS_FAILED) from None
        except TimeoutError:
            raise MailError(TIMED_OUT) from None
        except OSError:
            raise MailError(UNREACHABLE) from None

    def _connect(self, server: SmtpServer) -> smtplib.SMTP:
        if server.security == "tls":
            return smtplib.SMTP_SSL(
                server.host, server.port, timeout=self._timeout, context=self._context()
            )
        return smtplib.SMTP(server.host, server.port, timeout=self._timeout)
