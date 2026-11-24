"""The background phone sender: a 404 or 410 drops the phone's endpoint at once; a timeout, a
5xx or a 429 is retried 3 times with backoff, then given up and counted; another 4xx is given
up at once and counted; FCM refusing its access token gets a new one for the retry. It never
makes the caller wait."""

import logging
import time
from collections.abc import Callable, Iterator
from datetime import timedelta

import pytest
from fake_push_outbox import FakePushOutbox, TestPhone, service_account
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.app_settings.crypto import SecretBox, new_key_text, parse_key
from filament_tracker.db.engine import create_session_factory
from filament_tracker.db.models import Device, User
from filament_tracker.db.push_models import PushEndpoint
from filament_tracker.db.types import utcnow
from filament_tracker.domain.enums import PushRoute, Role
from filament_tracker.push.fcm_account import parse_service_account
from filament_tracker.push.firebase import Firebase, FirebaseClient
from filament_tracker.push.keys import vapid_keys
from filament_tracker.push.messages import Outcome, Push
from filament_tracker.push.sender import RETRIES, PushSender

SHORT = (0.01, 0.01, 0.01)
PHONE = "phone-1"
PUSH = Push(PHONE, b'{"kind":"low_stock"}')


def wait_for(condition: Callable[[], bool], timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.005)


@pytest.fixture
def sessions(engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(engine)


@pytest.fixture
def phone(sessions: sessionmaker[Session]) -> TestPhone:
    """A user's phone, registered for phone notifications."""
    phone = TestPhone()
    subscription = phone.subscription()
    with sessions() as session:
        user = User(username="sam", password_hash="x", role=Role.VIEWER)  # noqa: S106 - test value
        device = Device(id=PHONE, name="Pixel", token_hash="h", user=user)  # noqa: S106 - test value
        session.add(device)
        session.add(
            PushEndpoint(
                device_id=PHONE,
                route=PushRoute.WEB_PUSH,
                endpoint=phone.endpoint,
                p256dh=subscription["p256dh"],
                auth=subscription["auth"],
            )
        )
        session.commit()
    return phone


@pytest.fixture
def pushes() -> FakePushOutbox:
    return FakePushOutbox()


@pytest.fixture
def sender(
    sessions: sessionmaker[Session], pushes: FakePushOutbox, phone: TestPhone
) -> Iterator[PushSender]:
    keys = vapid_keys(sessions, SecretBox(parse_key(new_key_text())))
    sender = PushSender(pushes, sessions, keys, retries=SHORT)
    sender.start()
    yield sender
    sender.stop()


def _endpoint(sessions: sessionmaker[Session]) -> PushEndpoint | None:
    with sessions() as session:
        return session.get(PushEndpoint, PHONE)


def test_retries_add_up_to_about_15_minutes() -> None:
    assert len(RETRIES) == 3
    assert RETRIES == tuple(sorted(RETRIES))
    assert sum(RETRIES) == 15 * 60


def test_a_success_is_recorded(
    sender: PushSender, pushes: FakePushOutbox, sessions: sessionmaker[Session], phone: TestPhone
) -> None:
    sender.send_later([PUSH])

    wait_for(sender.idle)
    [message] = pushes.sent
    assert phone.decrypt(message) == {"kind": "low_stock"}
    endpoint = _endpoint(sessions)
    assert endpoint is not None and endpoint.last_success_at is not None
    assert endpoint.failures == 0


@pytest.mark.parametrize("status", [404, 410])
def test_a_gone_endpoint_is_dropped_at_once(
    sender: PushSender, pushes: FakePushOutbox, sessions: sessionmaker[Session], status: int
) -> None:
    pushes.answer(status)

    sender.send_later([PUSH])

    wait_for(sender.idle)
    assert pushes.attempts == 1
    assert _endpoint(sessions) is None


@pytest.mark.parametrize("failure", [None, 500, 503, 429])
def test_other_failures_are_retried_then_sent(
    sender: PushSender, pushes: FakePushOutbox, failure: int | None
) -> None:
    pushes.answer(failure, failure)

    sender.send_later([PUSH])

    wait_for(lambda: len(pushes.sent) == 1)
    assert pushes.attempts == 3


def test_after_3_retries_it_is_given_up_and_counted(
    sender: PushSender,
    pushes: FakePushOutbox,
    sessions: sessionmaker[Session],
    caplog: pytest.LogCaptureFixture,
    phone: TestPhone,
) -> None:
    caplog.set_level(logging.WARNING)
    pushes.answer(503, 503, 503, 503)

    sender.send_later([PUSH])

    wait_for(lambda: pushes.attempts == 4)
    wait_for(sender.idle)
    endpoint = _endpoint(sessions)
    assert endpoint is not None and endpoint.failures == 1
    assert "given up after 4 tries" in caplog.text
    assert phone.endpoint not in caplog.text
    # The next success clears the count.
    sender.send_later([PUSH])
    wait_for(sender.idle)
    endpoint = _endpoint(sessions)
    assert endpoint is not None and endpoint.failures == 0


def test_giving_up_counts_but_leaves_dropping_a_stale_endpoint_to_the_sweep(
    sender: PushSender, pushes: FakePushOutbox, sessions: sessionmaker[Session]
) -> None:
    with sessions() as session:
        session.get(PushEndpoint, PHONE).last_success_at = utcnow() - timedelta(days=31)
        session.commit()
    pushes.answer(503, 503, 503, 503)

    sender.send_later([PUSH])

    wait_for(lambda: pushes.attempts == 4)
    wait_for(sender.idle)
    endpoint = _endpoint(sessions)
    assert endpoint is not None and endpoint.failures == 1


def test_a_revoked_phone_or_a_disabled_user_gets_nothing(
    sender: PushSender, pushes: FakePushOutbox, sessions: sessionmaker[Session]
) -> None:
    for change in ("revoked", "disabled"):
        with sessions() as session:
            device = session.get(Device, PHONE)
            if change == "revoked":
                device.revoked_at = utcnow()
            else:
                device.revoked_at = None
                device.user.disabled_at = utcnow()
            session.commit()

        assert sender.send_now(PUSH).outcome == Outcome.NOWHERE
    assert pushes.attempts == 0


def test_send_now_waits_for_the_result_without_retrying(
    sender: PushSender, pushes: FakePushOutbox, sessions: sessionmaker[Session]
) -> None:
    pushes.answer(500)

    result = sender.send_now(PUSH)

    assert result.outcome == Outcome.FAILED
    assert result.message == "The push service answered 500."
    assert pushes.attempts == 1
    endpoint = _endpoint(sessions)
    assert endpoint is not None and endpoint.failures == 0
    assert sender.send_now(PUSH).outcome == Outcome.SENT


def test_an_unexpected_error_is_a_failure_logged_by_type_only(
    sessions: sessionmaker[Session], phone: TestPhone, caplog: pytest.LogCaptureFixture
) -> None:
    class Broken:
        def post(self, message: object) -> int:
            raise RuntimeError(f"secret detail {phone.endpoint}")

    caplog.set_level(logging.WARNING)
    keys = vapid_keys(sessions, SecretBox(parse_key(new_key_text())))
    sender = PushSender(Broken(), sessions, keys, retries=())

    result = sender.send_now(PUSH)

    assert result.outcome == Outcome.FAILED
    assert result.message == "The phone notification couldn't be sent."
    assert "RuntimeError" in caplog.text
    assert "secret detail" not in caplog.text


def test_stopping_ends_retries(sessions: sessionmaker[Session], phone: TestPhone) -> None:
    pushes = FakePushOutbox()
    pushes.answer(503)
    keys = vapid_keys(sessions, SecretBox(parse_key(new_key_text())))
    sender = PushSender(pushes, sessions, keys, retries=(30.0,))
    sender.start()
    sender.send_later([PUSH])
    wait_for(lambda: pushes.attempts == 1)

    started = time.monotonic()
    sender.stop()

    assert time.monotonic() - started < 2
    assert pushes.attempts == 1


@pytest.fixture
def fcm_sender(
    sessions: sessionmaker[Session], pushes: FakePushOutbox, phone: TestPhone
) -> Iterator[PushSender]:
    """A sender with Firebase set up, and the phone registered with an FCM token."""
    with sessions() as session:
        endpoint = session.get(PushEndpoint, PHONE)
        endpoint.route, endpoint.endpoint = PushRoute.FCM, "fcm-token"
        endpoint.p256dh = endpoint.auth = None
        session.commit()
    setup = Firebase(
        FirebaseClient("rollcall-test", "1:1:android:ab", "AIzaKey", "1"),
        parse_service_account(service_account().json),
    )
    keys = vapid_keys(sessions, SecretBox(parse_key(new_key_text())))
    sender = PushSender(pushes, sessions, keys, firebase=lambda: setup, retries=SHORT)
    sender.start()
    yield sender
    sender.stop()


def _given_up_at_once(
    sender: PushSender, pushes: FakePushOutbox, sessions: sessionmaker[Session]
) -> None:
    sender.send_later([PUSH])

    wait_for(lambda: pushes.attempts == 1)
    wait_for(sender.idle)
    assert pushes.attempts == 1
    endpoint = _endpoint(sessions)
    assert endpoint is not None and endpoint.failures == 1


@pytest.mark.parametrize("status", [400, 401, 403, 413])
def test_another_4xx_is_given_up_at_once_and_counted(
    sender: PushSender, pushes: FakePushOutbox, sessions: sessionmaker[Session], status: int
) -> None:
    pushes.answer(status)

    _given_up_at_once(sender, pushes, sessions)


@pytest.mark.parametrize("status", [400, 403])
def test_another_4xx_from_fcm_is_given_up_at_once_and_counted(
    fcm_sender: PushSender, pushes: FakePushOutbox, sessions: sessionmaker[Session], status: int
) -> None:
    pushes.answer(status)

    _given_up_at_once(fcm_sender, pushes, sessions)


def test_fcm_refusing_the_access_token_asks_for_a_new_one_and_tries_again(
    fcm_sender: PushSender, pushes: FakePushOutbox, sessions: sessionmaker[Session]
) -> None:
    pushes.answer(401)

    fcm_sender.send_later([PUSH])

    wait_for(lambda: len(pushes.sent) == 1)
    assert pushes.attempts == 2
    assert len(pushes.assertions) == 2
    [sent] = pushes.sent
    assert sent.headers["Authorization"] == "Bearer fake-access-token-2"


def test_fcm_answering_404_drops_the_token_at_once(
    fcm_sender: PushSender, pushes: FakePushOutbox, sessions: sessionmaker[Session]
) -> None:
    pushes.answer(404)

    fcm_sender.send_later([PUSH])

    wait_for(lambda: _endpoint(sessions) is None)
    assert pushes.attempts == 1


@pytest.mark.parametrize("failure", [None, 500, 429])
def test_fcm_retries_a_timeout_5xx_or_429(
    fcm_sender: PushSender, pushes: FakePushOutbox, failure: int | None
) -> None:
    pushes.answer(failure, failure)

    fcm_sender.send_later([PUSH])

    wait_for(lambda: len(pushes.sent) == 1)
    assert pushes.attempts == 3


def test_fcm_gives_up_after_3_retries_and_counts_it(
    fcm_sender: PushSender, pushes: FakePushOutbox, sessions: sessionmaker[Session]
) -> None:
    pushes.answer(503, 503, 503, 503)

    fcm_sender.send_later([PUSH])

    wait_for(lambda: pushes.attempts == 4)
    wait_for(fcm_sender.idle)
    endpoint = _endpoint(sessions)
    assert endpoint is not None and endpoint.failures == 1


def test_the_start_of_failures_since_the_last_success_is_kept(
    sender: PushSender, pushes: FakePushOutbox, sessions: sessionmaker[Session]
) -> None:
    pushes.answer(*[503] * 8)

    sender.send_later([PUSH])
    wait_for(lambda: pushes.attempts == 4)
    wait_for(sender.idle)
    first = _endpoint(sessions)
    assert first is not None and first.failing_since is not None
    sender.send_later([PUSH])
    wait_for(lambda: pushes.attempts == 8)
    wait_for(sender.idle)
    second = _endpoint(sessions)
    assert second is not None and second.failures == 2
    assert second.failing_since == first.failing_since

    sender.send_later([PUSH])
    wait_for(sender.idle)
    cleared = _endpoint(sessions)
    assert cleared is not None and cleared.failing_since is None
