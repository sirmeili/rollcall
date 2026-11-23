"""The kinds of notification: who may choose each, and what each channel defaults to.

This is the server's list, and the source of truth: the account API gives the web app the
kinds a user may choose, in this order, and the resolver (recipients.py) sends each only to
people who may choose it. The web app mirrors the kinds in `web/src/lib/api/types.ts`, and
how it names each in `web/src/lib/notifications.ts`.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from filament_tracker.db.models import User
from filament_tracker.domain.enums import Channel, NotificationKind, Role


def _editors(user: User) -> bool:
    return user.role.allows(Role.EDITOR)


def _admins(user: User) -> bool:
    return user.role.allows(Role.ADMIN)


def _requesters(user: User) -> bool:
    """Requester counts as the permission it is, apart from the role (ADR-0017)."""
    return user.requester


def _everyone(user: User) -> bool:
    return True


def _on(user: User) -> bool:
    return True


def _off(user: User) -> bool:
    return False


@dataclass(frozen=True)
class Kind:
    kind: NotificationKind
    # Whether the user's role (or Requester) lets them choose it, and so be told it.
    may_choose: Callable[[User], bool]
    # What each channel is for a user who hasn't chosen.
    defaults: Mapping[Channel, Callable[[User], bool]]
    # Whether anyone who has made a request may choose it too: their requests stay theirs
    # after they lose Requester, so they still hear about them (ADR-0017).
    request_owners: bool = False


def _email(on: Callable[[User], bool]) -> Mapping[Channel, Callable[[User], bool]]:
    """The defaults: `on` for Email, and on for Phone for every kind the user may choose, so
    setting up the phone app is enough to start hearing."""
    return {Channel.EMAIL: on, Channel.PHONE: _on}


KINDS: dict[NotificationKind, Kind] = {
    k.kind: k
    for k in (
        Kind(NotificationKind.NEW_REQUEST, _editors, _email(_admins)),
        Kind(NotificationKind.REQUEST_UPDATE, _requesters, _email(_on), request_owners=True),
        Kind(NotificationKind.NEW_PHOTO, _requesters, _email(_on), request_owners=True),
        Kind(NotificationKind.LOW_STOCK, _everyone, _email(_off)),
        Kind(NotificationKind.SUGGESTION, _editors, _email(_off)),
        Kind(NotificationKind.NEARLY_OUT, _everyone, _email(_off)),
        Kind(NotificationKind.BACKUP_FAILED, _admins, _email(_off)),
    )
}


def may_choose(user: User, kind: NotificationKind, *, has_requests: bool) -> bool:
    """Whether the kind is listed for the user: their role (or Requester) may choose it, or
    it is about requests and they have made one. Notifications never reads print requests
    (ADR-0014), so the caller says whether they have."""
    found = KINDS[kind]
    return found.may_choose(user) or (has_requests and found.request_owners)


def default(user: User, kind: NotificationKind, channel: Channel) -> bool:
    return KINDS[kind].defaults[channel](user)
