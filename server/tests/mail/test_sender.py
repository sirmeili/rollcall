"""The background sender: it never makes the caller wait, retries a failed send 3 times,
then logs and drops it, and keeps the last success and failure."""

import logging
import threading
import time
from collections.abc import Callable, Iterator
from email.message import EmailMessage

import pytest
from fake_outbox import FakeOutbox, html_of, text_of
from pydantic import SecretStr

from filament_tracker.mail.message import Email
from filament_tracker.mail.sender import RETRIES, MailSender
from filament_tracker.mail.transport import MailError, SmtpServer

PASSWORD = "smtp-password-value-1234"  # noqa: S105 - test value
SERVER = SmtpServer(
    host="smtp.example.com",
    port=587,
    security="starttls",
    user="rollcall",
    password=SecretStr(PASSWORD),
    from_address="RollCall <rollcall@example.com>",
)
EMAIL = Email(
    to="sam@example.com",
    subject="Your print request was approved: Hook",
    text="Your request was approved.\n",
    html="<p>Your request was approved.</p>",
)
SHORT = (0.01, 0.01, 0.01)


def wait_for(condition: Callable[[], bool], timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.005)


@pytest.fixture
def outbox() -> FakeOutbox:
    return FakeOutbox()


@pytest.fixture
def server() -> list[SmtpServer | None]:
    """The saved settings the sender reads at each send; set [0] to None for email off."""
    return [SERVER]


@pytest.fixture
def sender(outbox: FakeOutbox, server: list[SmtpServer | None]) -> Iterator[MailSender]:
    sender = MailSender(outbox, lambda: server[0], retries=SHORT)
    sender.start()
    yield sender
    sender.stop()


def test_retries_add_up_to_about_15_minutes() -> None:
    assert len(RETRIES) == 3
    assert 14 * 60 <= sum(RETRIES) <= 16 * 60


def test_an_email_is_sent_as_plain_text_and_html(sender: MailSender, outbox: FakeOutbox) -> None:
    sender.send_later([EMAIL])

    wait_for(lambda: len(outbox.sent) == 1)
    [message] = outbox.sent
    assert message["To"] == "sam@example.com"
    assert message["From"] == "RollCall <rollcall@example.com>"
    assert message["Subject"] == "Your print request was approved: Hook"
    assert text_of(message) == "Your request was approved.\n"
    assert html_of(message).strip() == "<p>Your request was approved.</p>"
    assert sender.last_success is not None
    assert sender.last_failure is None


def test_the_caller_never_waits_for_the_mail_server(server: list[SmtpServer | None]) -> None:
    release = threading.Event()

    class SlowOutbox:
        def send(self, _: SmtpServer, __: EmailMessage) -> None:
            release.wait(5)

    sender = MailSender(SlowOutbox(), lambda: server[0], retries=SHORT)
    sender.start()
    try:
        started = time.monotonic()
        sender.send_later([EMAIL, EMAIL])
        assert time.monotonic() - started < 0.5
    finally:
        release.set()
        sender.stop()


def test_a_failed_send_is_retried_and_then_sent(sender: MailSender, outbox: FakeOutbox) -> None:
    outbox.fail(times=2, message="Can't reach the mail server. Check the host and port.")

    sender.send_later([EMAIL])

    wait_for(lambda: len(outbox.sent) == 1)
    assert outbox.attempts == 3
    assert sender.last_success is not None
    assert sender.last_failure is not None
    assert sender.last_failure.message == "Can't reach the mail server. Check the host and port."
    assert sender.last_failure.at <= sender.last_success


def test_after_3_retries_the_email_is_logged_and_dropped(
    sender: MailSender, outbox: FakeOutbox, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    outbox.fail(times=10, message="The mail server refused the user name or password.")

    sender.send_later([EMAIL])

    wait_for(lambda: "dropped" in caplog.text)
    time.sleep(0.1)
    assert outbox.attempts == 4
    assert outbox.sent == []
    assert sender.last_success is None
    assert sender.last_failure is not None
    assert sender.last_failure.message == "The mail server refused the user name or password."
    assert "refused the user name or password" in caplog.text


def test_one_failing_email_does_not_hold_up_the_next(
    outbox: FakeOutbox, server: list[SmtpServer | None]
) -> None:
    sender = MailSender(outbox, lambda: server[0], retries=(0.5, 0.5, 0.5))
    sender.start()
    try:
        outbox.fail(times=1)
        other = Email("alex@example.com", "Hello", "Hi\n", "<p>Hi</p>")
        sender.send_later([EMAIL, other])

        wait_for(lambda: len(outbox.sent) == 1, timeout=0.4)
        assert outbox.sent[0]["To"] == "alex@example.com"
        wait_for(lambda: len(outbox.sent) == 2)
    finally:
        sender.stop()


def test_with_email_off_nothing_is_sent(
    sender: MailSender, outbox: FakeOutbox, server: list[SmtpServer | None]
) -> None:
    server[0] = None
    assert sender.on is False

    sender.send_later([EMAIL])

    time.sleep(0.1)
    assert outbox.attempts == 0


def test_without_a_from_address_the_send_fails_and_says_why(
    sender: MailSender, outbox: FakeOutbox, server: list[SmtpServer | None]
) -> None:
    server[0] = SmtpServer("smtp.example.com", 587, "starttls", None, None, None)

    with pytest.raises(MailError, match="No from address"):
        sender.send_now(EMAIL)

    assert outbox.attempts == 0
    assert sender.last_failure is not None


def test_an_unexpected_error_never_reaches_the_status_or_log(
    server: list[SmtpServer | None], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    class BrokenOutbox:
        def send(self, _: SmtpServer, __: EmailMessage) -> None:
            raise RuntimeError(f"something went wrong with {PASSWORD}")

    sender = MailSender(BrokenOutbox(), lambda: server[0], retries=())

    with pytest.raises(MailError) as raised:
        sender.send_now(EMAIL)

    assert PASSWORD not in str(raised.value)
    assert sender.last_failure is not None
    assert PASSWORD not in sender.last_failure.message
    assert PASSWORD not in caplog.text


def test_stopping_drops_waiting_emails(outbox: FakeOutbox, server: list[SmtpServer | None]) -> None:
    sender = MailSender(outbox, lambda: server[0], retries=(60.0,))
    sender.start()
    outbox.fail(times=1)
    sender.send_later([EMAIL])
    wait_for(lambda: outbox.attempts == 1)

    started = time.monotonic()
    sender.stop()

    assert time.monotonic() - started < 1
    assert outbox.sent == []


def test_settings_that_cant_be_read_are_a_failed_attempt_that_is_retried(
    outbox: FakeOutbox, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    reads = []

    def server() -> SmtpServer:
        reads.append(1)
        if len(reads) == 1:
            raise ValueError(f"invalid literal for int(): {PASSWORD}")
        return SERVER

    sender = MailSender(outbox, server, retries=SHORT)
    sender.start()
    try:
        sender.send_later([EMAIL])

        wait_for(lambda: len(outbox.sent) == 1)
    finally:
        sender.stop()
    assert sender.last_failure is not None
    assert sender.last_failure.message == "The email settings couldn't be read."
    assert "ValueError" in caplog.text
    assert PASSWORD not in caplog.text
