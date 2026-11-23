"""Who is told: the one place that decides who gets a kind of notification.

A person is told when their role (or Requester, or having made a request) lets them choose
the kind, they chose it on that channel or haven't chosen and its default is on, their account
isn't disabled, and they didn't do the thing themselves. Each sender calls this; none decides
on its own.
"""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.models import User
from filament_tracker.db.notification_models import NotificationChoice
from filament_tracker.domain.enums import Channel, NotificationKind
from filament_tracker.notifications.kinds import default, may_choose


def recipients(
    session: Session,
    kind: NotificationKind,
    channel: Channel,
    *,
    actor: User | None,
    among: Iterable[User] | None = None,
    have_requests: bool = False,
) -> list[User]:
    """The users told about `kind` on `channel`, in the order of `among` (every user, by id,
    when not given). `actor` did the thing, and is never told; None when nobody did (a
    product going low stock, a backup failing). `have_requests` says everyone in `among` has
    made a request, as the requester told about their own request has."""
    if among is None:
        among = session.scalars(select(User).order_by(User.id))
    candidates = [
        user
        for user in among
        if user.disabled_at is None
        and (actor is None or user.id != actor.id)
        and may_choose(user, kind, has_requests=have_requests)
    ]
    chosen = dict(
        session.execute(
            select(NotificationChoice.user_id, NotificationChoice.on).where(
                NotificationChoice.kind == kind,
                NotificationChoice.channel == channel,
                NotificationChoice.user_id.in_([user.id for user in candidates]),
            )
        ).all()
    )
    return [user for user in candidates if chosen.get(user.id, default(user, kind, channel))]


def email_recipients(
    session: Session,
    kind: NotificationKind,
    *,
    actor: User | None,
    among: Iterable[User] | None = None,
    have_requests: bool = False,
) -> list[str]:
    """The addresses to email about `kind`: its recipients by email who have an address."""
    return [
        user.email
        for user in recipients(
            session, kind, Channel.EMAIL, actor=actor, among=among, have_requests=have_requests
        )
        if user.email is not None
    ]
