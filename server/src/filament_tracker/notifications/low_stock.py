"""Low stock: when the database poll sees a product go from not low to low stock, a
notification to each person the resolver tells, about Inventory searched for the product."""

from collections.abc import Sequence
from urllib.parse import quote

from sqlalchemy.orm import Session

from filament_tracker.domain.enums import NotificationKind
from filament_tracker.notifications.notification import Notification
from filament_tracker.notifications.notifier import Notifier
from filament_tracker.poll import Changes
from filament_tracker.services.stock_snapshot import ProductState

LOW_STOCK_SUBJECT = "Low stock: {product}"
LOW_STOCK_SENTENCE = "{product} is low: {n} Sealed spools left."
OPEN_INVENTORY = "Open Inventory"


def low_stock(products: Sequence[ProductState]) -> list[Notification]:
    """One notification per product."""
    return [
        Notification(
            NotificationKind.LOW_STOCK,
            subject=LOW_STOCK_SUBJECT.format(product=product.name),
            sentence=LOW_STOCK_SENTENCE.format(product=product.name, n=product.sealed),
            # Inventory, searched for the product.
            path=f"/?q={quote(product.name, safe='')}",
            link_text=OPEN_INVENTORY,
        )
        for product in products
    ]


class LowStockNotifications:
    """The poll's listener that notifies about products that became low stock."""

    def __init__(self, notifier: Notifier) -> None:
        self._notifier = notifier

    def __call__(self, session: Session, changes: Changes) -> None:
        if changes.became_low:
            self._notifier.send(session, lambda: low_stock(changes.became_low))
