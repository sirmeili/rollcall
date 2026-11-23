"""A notification, said once for every channel: what happened, the page it is about, and who
may be told. Each channel asks the resolver who is told on it, then sends its own way: an
email to each address (notifications/email.py), a Web Push to each phone (phone.py)."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from filament_tracker.db.models import User
from filament_tracker.domain.enums import Channel, NotificationKind
from filament_tracker.notifications.recipients import recipients


@dataclass(frozen=True)
class Notification:
    kind: NotificationKind
    # The email's subject, and a phone notification's title: one line.
    subject: str
    # The one sentence saying what happened: the email's first line, and a phone
    # notification's text.
    sentence: str
    # The web app's page it is about ("/settings").
    path: str
    # What the email's link says.
    link_text: str
    # Labelled details, in the email only.
    details: tuple[tuple[str, str], ...] = ()
    # JPEGs shown in the email.
    photos: tuple[bytes, ...] = ()
    # The server path of the photo a phone notification shows, which the phone downloads
    # with its sign-in; None for none.
    photo: str | None = None
    # Who did it, and is never told; None when nobody did.
    actor: User | None = None
    # Only these may be told (everyone, when None).
    among: tuple[User, ...] | None = None
    # Everyone in `among` has made a request, as a requester told about their own has.
    have_requests: bool = False

    def told(self, session: Session, channel: Channel) -> list[User]:
        """The users told about it on `channel`."""
        return recipients(
            session,
            self.kind,
            channel,
            actor=self.actor,
            among=self.among,
            have_requests=self.have_requests,
        )
