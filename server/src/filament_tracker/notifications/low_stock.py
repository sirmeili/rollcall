"""Low stock emails: when the database poll sees a product go from not low to low stock, an
email to each person the resolver tells, linking to Inventory searched for the product.

Links use PUBLIC_URL only; without it, the emails have no link.
"""

from collections.abc import Callable, Sequence
from urllib.parse import quote

from sqlalchemy.orm import Session

from filament_tracker.domain.enums import NotificationKind
from filament_tracker.mail.message import Email
from filament_tracker.mail.sender import MailSender
from filament_tracker.notifications.email import build_and_send, compose, link
from filament_tracker.notifications.recipients import email_recipients
from filament_tracker.poll import Changes
from filament_tracker.services.stock_snapshot import ProductState

LOW_STOCK_SUBJECT = "Low stock: {product}"
LOW_STOCK_SENTENCE = "{product} is low: {n} Sealed spools left."
OPEN_INVENTORY = "Open Inventory"


def low_stock_emails(
    session: Session, products: Sequence[ProductState], public_url: str | None
) -> list[Email]:
    """One email per product to each person told about Low stock."""
    to = email_recipients(session, NotificationKind.LOW_STOCK, actor=None)
    return [
        compose(
            address,
            subject=LOW_STOCK_SUBJECT.format(product=product.name),
            sentence=LOW_STOCK_SENTENCE.format(product=product.name, n=product.sealed),
            # Inventory, searched for the product.
            link=link(public_url, f"/?q={quote(product.name, safe='')}"),
            link_text=OPEN_INVENTORY,
        )
        for product in products
        for address in to
    ]


class LowStockEmails:
    """The poll's listener that emails about products that became low stock, while email is
    on. `public_url` reads PUBLIC_URL when the emails are built."""

    def __init__(self, mail: MailSender, public_url: Callable[[], str | None]) -> None:
        self._mail = mail
        self._public_url = public_url

    def __call__(self, session: Session, changes: Changes) -> None:
        if changes.became_low:
            build_and_send(
                self._mail,
                lambda url: low_stock_emails(session, changes.became_low, url),
                self._public_url,
            )
