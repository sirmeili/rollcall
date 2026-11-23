"""What Home Assistant shows, read from the database in one go."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from filament_tracker.services import queries
from filament_tracker.services.shopping_list import duplicates
from filament_tracker.services.stock_snapshot import ProductState, product_states


@dataclass(frozen=True)
class Snapshot:
    products: tuple[ProductState, ...]
    total_sealed: int
    total_open: int
    in_review: int

    @property
    def total_spools(self) -> int:
        """Spools still in hand: sealed and open, not used up."""
        return self.total_sealed + self.total_open

    @property
    def low_stock(self) -> tuple[ProductState, ...]:
        return tuple(p for p in self.products if p.low_stock)


def take_snapshot(session: Session) -> Snapshot:
    products = product_states(session)
    # The same total as the Review page's badge, possible duplicates included.
    in_review = (
        len(queries.flagged_events(session))
        + len(queries.unidentified_tags(session))
        + len(queries.likely_empty(session))
        + len(duplicates.open_duplicates(session))
    )
    return Snapshot(
        products,
        total_sealed=sum(p.sealed for p in products),
        total_open=sum(p.open for p in products),
        in_review=in_review,
    )
