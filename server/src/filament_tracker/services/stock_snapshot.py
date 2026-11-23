"""Each product's stock, read from the database in one go: what the database poll watches for
low stock, and what Home Assistant shows for each product."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from filament_tracker.domain.enums import SpoolState
from filament_tracker.services import queries


@dataclass(frozen=True)
class ProductState:
    id: int
    name: str
    filament_type: str
    color_rgba: str
    sealed: int
    open: int
    low_stock: bool
    low_stock_threshold: int


def product_states(session: Session) -> tuple[ProductState, ...]:
    return tuple(
        ProductState(
            id=item.product.id,
            name=item.product.display_name,
            filament_type=item.product.filament_type,
            color_rgba=item.product.color_rgba,
            sealed=item.counts.get(SpoolState.SEALED, 0),
            open=item.counts.get(SpoolState.OPEN, 0),
            low_stock=item.low_stock,
            low_stock_threshold=item.product.low_stock_threshold,
        )
        for item in queries.inventory(session)
    )
