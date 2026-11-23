"""Nearly out: when the database poll sees a spool in an AMS go from not nearly out to nearly
out, a notification to each person the resolver tells, about that spool."""

from collections.abc import Sequence

from sqlalchemy.orm import Session

from filament_tracker.domain.enums import NotificationKind
from filament_tracker.notifications.notification import Notification
from filament_tracker.notifications.notifier import Notifier
from filament_tracker.poll import Changes, NearlyOutSpool

NEARLY_OUT_SUBJECT = "Nearly out: {product} in {slot}"
NEARLY_OUT_SENTENCE = "{product} in {slot} has about {n}% left."
OPEN_SPOOL = "Open the spool"


def nearly_out(spools: Sequence[NearlyOutSpool]) -> list[Notification]:
    """One notification per spool."""
    return [
        Notification(
            NotificationKind.NEARLY_OUT,
            subject=NEARLY_OUT_SUBJECT.format(product=spool.product, slot=spool.slot),
            sentence=NEARLY_OUT_SENTENCE.format(
                product=spool.product, slot=spool.slot, n=spool.remaining_pct
            ),
            path=f"/spools/{spool.id}",
            link_text=OPEN_SPOOL,
        )
        for spool in spools
    ]


class NearlyOutNotifications:
    """The poll's listener that notifies about spools that became nearly out."""

    def __init__(self, notifier: Notifier) -> None:
        self._notifier = notifier

    def __call__(self, session: Session, changes: Changes) -> None:
        if changes.became_nearly_out:
            self._notifier.send(session, lambda: nearly_out(changes.became_nearly_out))
