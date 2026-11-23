"""A phone notification's payload: its kind, title, text and path as JSON, cut short to stay
under the 4 KB a Web Push may carry once encrypted."""

import json

from fake_push_outbox import TestPhone
from sqlalchemy import Engine

from filament_tracker.app_settings.crypto import SecretBox, new_key_text, parse_key
from filament_tracker.db.engine import create_session_factory
from filament_tracker.push.keys import vapid_keys
from filament_tracker.push.payload import phone_payload
from filament_tracker.push.webpush import Subscription, web_push


def test_a_short_payload_is_kept_whole() -> None:
    payload = phone_payload("low_stock", "Low stock: Black", 'Black "PLA" is low.', "/?q=Black")

    assert json.loads(payload) == {
        "kind": "low_stock",
        "title": "Low stock: Black",
        "text": 'Black "PLA" is low.',
        "path": "/?q=Black",
    }


def test_a_long_text_then_title_is_cut_short_to_fit() -> None:
    title = "Your print is done: " + "Ü" * 3000
    text = 'Your print "' + '"' * 3000 + '" is done.'

    payload = phone_payload("request_update", title, text, "/requests/7")

    assert len(payload) <= 3072
    found = json.loads(payload)
    assert found["text"] == "…"
    assert found["title"].startswith("Your print is done: ÜÜ")
    assert found["title"].endswith("…")
    assert found["path"] == "/requests/7"


def test_the_encrypted_push_stays_under_4_kb(engine: Engine) -> None:
    keys = vapid_keys(create_session_factory(engine), SecretBox(parse_key(new_key_text())))
    phone = TestPhone()
    sub = phone.subscription()
    payload = phone_payload("new_request", "x" * 5000, "y" * 5000, "/requests/1")

    message = web_push(Subscription(phone.endpoint, sub["p256dh"], sub["auth"]), payload, keys)

    assert len(message.body) < 4096
    assert phone.decrypt(message)["path"] == "/requests/1"
