"""The Suggestion notification: each Editor and Admin the notification resolver tells hears
that someone suggested a product or catalog color for the shopping list, never the one who
suggested it. It is about the Shopping list, where suggestions wait at the top."""

from sqlalchemy.orm import Session

from filament_tracker.db.models import Product, User
from filament_tracker.db.shopping_models import Suggestion
from filament_tracker.domain.enums import NotificationKind
from filament_tracker.notifications.notification import Notification
from filament_tracker.services.catalog_links import load_index

SUGGESTION_SUBJECT = "New suggestion from {user}: {name}"
SUGGESTION_SENTENCE = "{user} suggested {spools} of {name} for the shopping list."
# From a token, which acts for no user.
SUGGESTION_NO_USER_SUBJECT = "New suggestion: {name}"
SUGGESTION_NO_USER_SENTENCE = "Someone suggested {spools} of {name} for the shopping list."
OPEN_SHOPPING_LIST = "Open the shopping list"


def suggested(session: Session, suggestion: Suggestion) -> Notification:
    """The Suggestion notification about `suggestion`."""
    user = session.get(User, suggestion.suggested_by) if suggestion.suggested_by else None
    name = _name(session, suggestion)
    spools = f"{suggestion.spools} spool{'' if suggestion.spools == 1 else 's'}"
    if user is None:
        subject = SUGGESTION_NO_USER_SUBJECT.format(name=name)
        sentence = SUGGESTION_NO_USER_SENTENCE.format(spools=spools, name=name)
    else:
        subject = SUGGESTION_SUBJECT.format(user=user.username, name=name)
        sentence = SUGGESTION_SENTENCE.format(user=user.username, spools=spools, name=name)
    return Notification(
        NotificationKind.SUGGESTION,
        subject=subject,
        sentence=sentence,
        path="/shopping-list",
        link_text=OPEN_SHOPPING_LIST,
        actor=user,
    )


def _name(session: Session, suggestion: Suggestion) -> str:
    """The product's name, or the catalog color's name and line, as the Shopping list shows
    them."""
    if suggestion.product_id is not None:
        return session.get(Product, suggestion.product_id).display_name
    color = load_index(session).colors[suggestion.catalog_uuid]
    return f"{color.name} {color.line}"
