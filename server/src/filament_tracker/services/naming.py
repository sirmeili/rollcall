"""Product names: the default name and the catalog name (see GLOSSARY.md).

Scans, the AMS and making a product from a catalog color all name products here, so the
two forms are defined once. A product that gains a catalog link while it still has its
default name takes its catalog name.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from filament_tracker.db.models import Product
from filament_tracker.services.catalog_links import IndexedColor, newly_linked

# Product.display_name is a String(100).
NAME_LENGTH = 100


def default_name(kind: str, color_rgba: str) -> str:
    """A product's name when first seen on a tag or in the AMS: its material, then ` #` and
    the first six hex digits of its color, such as PLA Basic #FF0000."""
    return f"{kind} #{color_rgba[:6]}"


def is_default_name(name: str, color_rgba: str) -> bool:
    """Whether `name` is the default name for a product of this color: it ends with ` #` and
    the color's first six hex digits, compared without regard to case. A typed name that
    happens to end that way counts."""
    return name.casefold().endswith(f" #{color_rgba[:6]}".casefold())


def catalog_name(color_name: str, line_name: str) -> str:
    """A catalog color's name, a space, then its filament line's name, such as Hot Pink PLA
    Basic, cut to fit a product's name."""
    return f"{color_name} {line_name}"[:NAME_LENGTH]


@dataclass(frozen=True)
class Before:
    """A product as it was before it may have gained a link."""

    # Whether it had an effective link.
    linked: bool
    # Its color: an AMS-made name ends with the AMS's color, not the tag's.
    color_rgba: str


def name_after_new_link(
    product: Product, before: Before, linked_color: IndexedColor | None
) -> None:
    """Give the product its catalog name when it gained an effective link (had none before,
    is linked to `linked_color` now) and still has the default name for its color before."""
    if before.linked or linked_color is None:
        return
    if is_default_name(product.display_name, before.color_rgba):
        product.display_name = catalog_name(linked_color.name, linked_color.line)


def name_newly_linked(session: Session, linked_before: set[int]) -> None:
    """After a sync: give each product that gained an effective link, and still has its
    default name, its catalog name. `linked_before` holds the IDs of the products that had
    an effective link before the sync."""
    for product, color in newly_linked(session, linked_before):
        name_after_new_link(product, Before(linked=False, color_rgba=product.color_rgba), color)
