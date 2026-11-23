"""Nearly out emails: when the database poll sees a spool in an AMS go from not nearly out to
nearly out, an email to each person the resolver tells, linking to that spool.

Links use PUBLIC_URL only; without it, the emails have no link.
"""

from collections.abc import Callable, Sequence

from sqlalchemy.orm import Session

from filament_tracker.domain.enums import NotificationKind
from filament_tracker.mail.message import Email
from filament_tracker.mail.sender import MailSender
from filament_tracker.notifications.email import build_and_send, compose, link
from filament_tracker.notifications.recipients import email_recipients
from filament_tracker.poll import Changes, NearlyOutSpool

NEARLY_OUT_SUBJECT = "Nearly out: {product} in {slot}"
NEARLY_OUT_SENTENCE = "{product} in {slot} has about {n}% left."
OPEN_SPOOL = "Open the spool"


def nearly_out_emails(
    session: Session, spools: Sequence[NearlyOutSpool], public_url: str | None
) -> list[Email]:
    """One email per spool to each person told about Nearly out."""
    to = email_recipients(session, NotificationKind.NEARLY_OUT, actor=None)
    return [
        compose(
            address,
            subject=NEARLY_OUT_SUBJECT.format(product=spool.product, slot=spool.slot),
            sentence=NEARLY_OUT_SENTENCE.format(
                product=spool.product, slot=spool.slot, n=spool.remaining_pct
            ),
            link=link(public_url, f"/spools/{spool.id}"),
            link_text=OPEN_SPOOL,
        )
        for spool in spools
        for address in to
    ]


class NearlyOutEmails:
    """The poll's listener that emails about spools that became nearly out, while email is
    on. `public_url` reads PUBLIC_URL when the emails are built."""

    def __init__(self, mail: MailSender, public_url: Callable[[], str | None]) -> None:
        self._mail = mail
        self._public_url = public_url

    def __call__(self, session: Session, changes: Changes) -> None:
        if changes.became_nearly_out:
            build_and_send(
                self._mail,
                lambda url: nearly_out_emails(session, changes.became_nearly_out, url),
                self._public_url,
            )
