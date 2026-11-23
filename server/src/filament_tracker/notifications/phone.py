"""The phone channel: a Web Push about each notification to each registered phone of each
person told about it by Phone. A shared phone, a revoked one and a disabled user's never get
one. The push carries the kind, the email's subject and sentence, the page's path and the
photo to show, if any."""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.models import Device, User
from filament_tracker.db.push_models import PushEndpoint
from filament_tracker.domain.enums import Channel
from filament_tracker.notifications.notification import Notification
from filament_tracker.push.messages import Push, reachable
from filament_tracker.push.payload import phone_payload


def _phones(session: Session, user_ids: list[int]) -> dict[int, list[PushEndpoint]]:
    """Each user's registered phones that may get phone notifications."""
    found = session.scalars(
        select(PushEndpoint)
        .join(Device, PushEndpoint.device_id == Device.id)
        .where(Device.user_id.in_(user_ids))
        .order_by(PushEndpoint.device_id)
    )
    phones: dict[int, list[PushEndpoint]] = {}
    for endpoint in found:
        if reachable(endpoint):
            phones.setdefault(endpoint.device.user_id or 0, []).append(endpoint)
    return phones


def has_phone(session: Session, user: User) -> bool:
    """Whether the user has a registered phone that may get phone notifications."""
    return bool(_phones(session, [user.id]))


def phone_pushes(session: Session, notifications: Iterable[Notification]) -> list[Push]:
    """A push about each notification to each phone of each person told about it by Phone."""
    pushes = []
    for n in notifications:
        told = n.told(session, Channel.PHONE)
        if not told:
            continue
        payload = phone_payload(n.kind.value, n.subject, n.sentence, n.path, n.phone_photo)
        phones = _phones(session, [user.id for user in told])
        for user in told:
            pushes.extend(Push(phone.device_id, payload) for phone in phones.get(user.id, []))
    return pushes
