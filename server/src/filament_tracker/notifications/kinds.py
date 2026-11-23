"""The kinds of notification: who may choose each, and what each channel defaults to.

This is the one list. The account API gives the web app the kinds a user may choose, in
this order, and the resolver (recipients.py) sends each only to people who may choose it.
A kind is listed only once something sends it (`sent`); until then nobody sees it.
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
    # Something sends it; a kind is hidden from everyone until then.
    sent: bool = False


KINDS: dict[NotificationKind, Kind] = {
    k.kind: k
    for k in (
        Kind(NotificationKind.NEW_REQUEST, _editors, {Channel.EMAIL: _admins}, sent=True),
        Kind(NotificationKind.REQUEST_UPDATE, _requesters, {Channel.EMAIL: _on}, sent=True),
        Kind(NotificationKind.NEW_PHOTO, _requesters, {Channel.EMAIL: _on}, sent=True),
        Kind(NotificationKind.LOW_STOCK, _everyone, {Channel.EMAIL: _off}, sent=True),
        Kind(NotificationKind.SUGGESTION, _editors, {Channel.EMAIL: _off}),
        Kind(NotificationKind.NEARLY_OUT, _everyone, {Channel.EMAIL: _off}),
        Kind(NotificationKind.BACKUP_FAILED, _admins, {Channel.EMAIL: _off}),
    )
}


def may_choose(user: User, kind: NotificationKind) -> bool:
    """Whether the kind is listed for the user: it is sent, and their role may choose it."""
    found = KINDS[kind]
    return found.sent and found.may_choose(user)


def default(user: User, kind: NotificationKind, channel: Channel) -> bool:
    return KINDS[kind].defaults[channel](user)
