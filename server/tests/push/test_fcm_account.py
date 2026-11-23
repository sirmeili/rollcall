"""A Firebase service-account key file: accepted only as JSON of a service account with an RSA
private key, and refused without repeating any of it."""

import json

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
from fake_push_outbox import service_account

from filament_tracker.push.fcm_account import PROBLEM, parse_service_account


def _with_key(pem: str) -> str:
    body = json.loads(service_account().json)
    body["private_key"] = pem
    return json.dumps(body)


def test_a_downloaded_key_is_read() -> None:
    made = service_account()

    account = parse_service_account(made.json)

    assert account.email == made.email
    assert "PRIVATE" not in repr(account)


@pytest.mark.parametrize(
    "text",
    [
        "[]",
        '{"type": "service_account", "client_email": "a@b"}',
        _with_key("-----BEGIN PRIVATE KEY-----\nsecret-not-a-key\n-----END PRIVATE KEY-----\n"),
        _with_key(
            ec.generate_private_key(ec.SECP256R1())
            .private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
            .decode()
        ),
    ],
)
def test_anything_else_is_refused_without_repeating_it(text: str) -> None:
    with pytest.raises(ValueError) as refused:
        parse_service_account(text)

    assert str(refused.value) == PROBLEM
    assert "secret-not-a-key" not in str(refused.value)
