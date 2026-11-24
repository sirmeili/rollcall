"""A Firebase service-account key: the JSON file Firebase's console downloads, which the
server signs its OAuth requests for FCM with.

Errors never repeat the key or any part of it.
"""

import json
from dataclasses import dataclass, field

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key

# The largest key file accepted: real ones are about 2.4 KB.
MAX_KEY_CHARS = 8192
PROBLEM = "use the service-account key file from Firebase, as JSON"


@dataclass(frozen=True)
class ServiceAccountKey:
    email: str
    # Never shown in a repr, so never in a log or a traceback.
    private_key: rsa.RSAPrivateKey = field(repr=False)


def parse_service_account(text: str) -> ServiceAccountKey:
    """The key in `text`, or ValueError with a message that never repeats it."""
    try:
        body = json.loads(text)
    except ValueError:
        raise ValueError(PROBLEM) from None
    if not isinstance(body, dict) or body.get("type") != "service_account":
        raise ValueError(PROBLEM)
    email = body.get("client_email")
    pem = body.get("private_key")
    if not isinstance(email, str) or not email or not isinstance(pem, str):
        raise ValueError(PROBLEM)
    try:
        key = load_pem_private_key(pem.encode(), password=None)
    except (ValueError, TypeError, UnsupportedAlgorithm):
        raise ValueError(PROBLEM) from None
    if not isinstance(key, rsa.RSAPrivateKey):
        raise ValueError(PROBLEM)
    return ServiceAccountKey(email, key)
