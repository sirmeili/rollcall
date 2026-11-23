"""Posting a Web Push: the push service's status comes back, redirects aren't followed, and a
timeout or an unreachable service is a PushError that never repeats the service's text."""

import httpx
import pytest

from filament_tracker.push.transport import HttpPushTransport, PushError
from filament_tracker.push.webpush import PushMessage

MESSAGE = PushMessage("https://push.example.com/up/abc", {"TTL": "60"}, b"sealed")


def test_it_posts_the_message_and_returns_the_status() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(201)

    assert HttpPushTransport(httpx.MockTransport(handle)).post(MESSAGE) == 201
    [request] = seen
    assert str(request.url) == MESSAGE.endpoint
    assert request.method == "POST"
    assert request.headers["TTL"] == "60"
    assert request.content == b"sealed"


def test_a_redirect_is_not_followed() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "https://elsewhere.example.com/"})

    assert HttpPushTransport(httpx.MockTransport(handle)).post(MESSAGE) == 302


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (httpx.ReadTimeout("secret text"), "The push service didn't answer in time."),
        (httpx.ConnectError("secret text"), "The push service couldn't be reached."),
    ],
)
def test_failures_are_push_errors_without_the_services_text(
    error: httpx.HTTPError, message: str
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise error

    with pytest.raises(PushError) as raised:
        HttpPushTransport(httpx.MockTransport(handle)).post(MESSAGE)

    assert str(raised.value) == message
