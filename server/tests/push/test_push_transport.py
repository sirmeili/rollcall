"""Posting a Web Push or FCM message: the push service's status comes back, redirects aren't
followed, and a timeout or an unreachable service is a PushError that never repeats the
service's text. FCM's access tokens come from Google's OAuth token endpoint, and only from it."""

from urllib.parse import parse_qs

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


def _token_transport(answer: httpx.Response, seen: list[httpx.Request]) -> HttpPushTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return answer

    return HttpPushTransport(httpx.MockTransport(handle))


def test_an_access_token_is_asked_for_at_google_with_the_assertion() -> None:
    seen: list[httpx.Request] = []
    answer = httpx.Response(200, json={"access_token": "ya29.abc", "expires_in": 3599})

    token = _token_transport(answer, seen).access_token("signed.jwt.here")

    assert (token.token, token.expires_in) == ("ya29.abc", 3599)
    [request] = seen
    assert str(request.url) == "https://oauth2.googleapis.com/token"
    assert parse_qs(request.content.decode()) == {
        "grant_type": ["urn:ietf:params:oauth:grant-type:jwt-bearer"],
        "assertion": ["signed.jwt.here"],
    }
    assert "ya29.abc" not in repr(token)


@pytest.mark.parametrize(
    ("answer", "message"),
    [
        (
            httpx.Response(400, json={"error": "invalid_grant"}),
            "Google refused the Firebase service-account key.",
        ),
        (
            httpx.Response(401, text="secret text"),
            "Google refused the Firebase service-account key.",
        ),
        (
            httpx.Response(500, text="secret text"),
            "Google's sign-in for Firebase couldn't be reached.",
        ),
        (
            httpx.Response(200, text="not json"),
            "Google's sign-in for Firebase couldn't be reached.",
        ),
        (
            httpx.Response(200, json={"expires_in": 10}),
            "Google's sign-in for Firebase couldn't be reached.",
        ),
        (
            httpx.Response(302, headers={"Location": "https://elsewhere.example.com/"}),
            "Google's sign-in for Firebase couldn't be reached.",
        ),
    ],
)
def test_a_token_that_cant_be_had_is_a_push_error_without_googles_text(
    answer: httpx.Response, message: str
) -> None:
    with pytest.raises(PushError) as raised:
        _token_transport(answer, []).access_token("signed.jwt.here")

    assert str(raised.value) == message


def test_google_out_of_reach_is_a_push_error() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("secret text")

    with pytest.raises(PushError) as raised:
        HttpPushTransport(httpx.MockTransport(handle)).access_token("signed.jwt.here")

    assert str(raised.value) == "Google's sign-in for Firebase couldn't be reached."
