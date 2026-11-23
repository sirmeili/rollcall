"""The Suggestion email: each Editor and Admin the notification resolver tells hears that
someone suggested a product or catalog color for the shopping list, never the one who
suggested it. It links to the Shopping list, where suggestions wait at the top; the link uses
PUBLIC_URL only, and without it the email has no link."""

from sqlalchemy.orm import Session

from filament_tracker.db.models import Product, User
from filament_tracker.db.shopping_models import Suggestion
from filament_tracker.domain.enums import NotificationKind
from filament_tracker.mail.message import Email
from filament_tracker.notifications.email import compose, link
from filament_tracker.notifications.recipients import email_recipients
from filament_tracker.services.catalog_links import load_index

SUGGESTION_SUBJECT = "New suggestion from {user}: {name}"
SUGGESTION_SENTENCE = "{user} suggested {spools} of {name} for the shopping list."
# From a token, which acts for no user.
SUGGESTION_NO_USER_SUBJECT = "New suggestion: {name}"
SUGGESTION_NO_USER_SENTENCE = "Someone suggested {spools} of {name} for the shopping list."
OPEN_SHOPPING_LIST = "Open the shopping list"


def suggestion_emails(
    session: Session, suggestion: Suggestion, public_url: str | None
) -> list[Email]:
    """A Suggestion email to each Editor and Admin the resolver tells about `suggestion`."""
    user = session.get(User, suggestion.suggested_by) if suggestion.suggested_by else None
    name = _name(session, suggestion)
    spools = f"{suggestion.spools} spool{'' if suggestion.spools == 1 else 's'}"
    if user is None:
        subject = SUGGESTION_NO_USER_SUBJECT.format(name=name)
        sentence = SUGGESTION_NO_USER_SENTENCE.format(spools=spools, name=name)
    else:
        subject = SUGGESTION_SUBJECT.format(user=user.username, name=name)
        sentence = SUGGESTION_SENTENCE.format(user=user.username, spools=spools, name=name)
    to_list = link(public_url, "/shopping-list")
    return [
        compose(to, subject=subject, sentence=sentence, link=to_list, link_text=OPEN_SHOPPING_LIST)
        for to in email_recipients(session, NotificationKind.SUGGESTION, actor=user)
    ]


def _name(session: Session, suggestion: Suggestion) -> str:
    """The product's name, or the catalog color's name and line, as the Shopping list shows
    them."""
    if suggestion.product_id is not None:
        return session.get(Product, suggestion.product_id).display_name
    color = load_index(session).colors[suggestion.catalog_uuid]
    return f"{color.name} {color.line}"
