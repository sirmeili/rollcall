"""FCM's OAuth access token: kept until 5 minutes before it expires, and asked for again for a
different service-account key."""

from fake_push_outbox import FakePushOutbox, assertion_claims, service_account

from filament_tracker.push.fcm import AccessTokens
from filament_tracker.push.fcm_account import parse_service_account


class Clock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


def test_a_token_is_kept_until_5_minutes_before_it_expires() -> None:
    pushes, clock = FakePushOutbox(), Clock()
    tokens = AccessTokens(pushes, clock)
    made = service_account()
    account = parse_service_account(made.json)

    first = tokens.get(account)
    clock.now += 3600 - 301
    kept = tokens.get(account)
    clock.now += 1
    renewed = tokens.get(account)

    assert first == kept == "fake-access-token-1"
    assert renewed == "fake-access-token-2"
    claims = assertion_claims(pushes.assertions[1], made)
    assert claims["iat"] == int(clock.now)


def test_a_different_key_asks_again() -> None:
    pushes = FakePushOutbox()
    tokens = AccessTokens(pushes, Clock())

    first = tokens.get(parse_service_account(service_account().json))
    second = tokens.get(parse_service_account(service_account().json))

    assert (first, second) == ("fake-access-token-1", "fake-access-token-2")
