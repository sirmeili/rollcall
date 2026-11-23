"""The server's VAPID key pair (RFC 8292): made on first start, stored with the private key
sealed by the settings key (ADR-0007), and never changed, since a new pair makes every phone
register again.

A database restored without its settings key can't open the private key. Then a new pair
is made and every Web Push endpoint is dropped, as they were registered with the old public
key; each phone registers again the next time it signs in or its endpoint changes.

Nothing here logs or returns the private key.
"""

import base64
import logging
from dataclasses import dataclass, field

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.app_settings.crypto import SecretBox, Unreadable
from filament_tracker.db.push_models import PushEndpoint, VapidKey
from filament_tracker.domain.enums import PushRoute

logger = logging.getLogger(__name__)

# The name the private key is sealed under, so it can't be moved to another secret.
SEALED_AS = "vapid_private_key"
KEY_ID = 1


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64url(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


@dataclass(frozen=True)
class VapidKeys:
    # Never shown in a repr, so never in a log or a traceback.
    private: ec.EllipticCurvePrivateKey = field(repr=False)
    # The uncompressed P-256 point, base64url: what phones register with.
    public: str


def _public(private: ec.EllipticCurvePrivateKey) -> str:
    return b64url(private.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint))


def _sealed(box: SecretBox, private: ec.EllipticCurvePrivateKey) -> str:
    raw = private.private_numbers().private_value.to_bytes(32, "big")
    return box.seal(SEALED_AS, b64url(raw))


def _opened(box: SecretBox, sealed: str) -> ec.EllipticCurvePrivateKey:
    value = int.from_bytes(unb64url(box.open(SEALED_AS, sealed)), "big")
    return ec.derive_private_key(value, ec.SECP256R1())


def _new(session: Session, box: SecretBox) -> VapidKeys:
    private = ec.generate_private_key(ec.SECP256R1())
    keys = VapidKeys(private, _public(private))
    session.merge(VapidKey(id=KEY_ID, private_key=_sealed(box, private), public_key=keys.public))
    return keys


def vapid_keys(sessions: sessionmaker[Session], box: SecretBox) -> VapidKeys:
    """The key pair, made now if there is none (or the stored one can't be opened)."""
    with sessions() as session:
        row = session.scalar(select(VapidKey).where(VapidKey.id == KEY_ID))
        if row is None:
            keys = _new(session, box)
            logger.info("made the VAPID key pair for phone notifications")
        else:
            try:
                return VapidKeys(_opened(box, row.private_key), row.public_key)
            except Unreadable:
                keys = _new(session, box)
                session.execute(delete(PushEndpoint).where(PushEndpoint.route == PushRoute.WEB_PUSH))
                logger.warning(
                    "the VAPID key can't be opened with this settings key, so a new one was "
                    "made; every phone registers for phone notifications again"
                )
        session.commit()
        return keys
