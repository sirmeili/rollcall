"""The shopping list's tables (Inventory). Only what people did is stored; each item's need
is worked out live (ADR-0021). Possible duplicates, a kind of Review item about products
made from catalog colors, are here too."""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from filament_tracker.db.models import Base, Product, User
from filament_tracker.db.types import str_enum, utcnow
from filament_tracker.domain.enums import DuplicateState, ShoppingAction, SuggestionStatus


class ShoppingListItemRow(Base):
    """What people set on a product's one shopping list item. A row with nothing in it is the
    same as no row."""

    __tablename__ = "shopping_list_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), unique=True)
    # Spools ordered and not yet arrived.
    on_order: Mapped[int] = mapped_column(default=0, server_default="0")
    # The size chosen on the item, in grams, to turn grams into spools.
    chosen_size_g: Mapped[int | None]
    # The need when it was dismissed: hidden while the need is at or below it.
    dismissed_need: Mapped[int | None]

    product: Mapped[Product] = relationship()


class HandReason(Base):
    """Spools an Editor or Admin added to a product's item by hand."""

    __tablename__ = "shopping_hand_reason"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), index=True)
    spools: Mapped[int]
    # None for the admin token or a machine token, which act for no user.
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    at: Mapped[datetime] = mapped_column(default=utcnow)

    product: Mapped[Product] = relationship()
    user: Mapped[User | None] = relationship()


class Suggestion(Base):
    """A Viewer's ask to put a product or a catalog color on the list. It counts toward
    nothing until an Editor or Admin adds it."""

    __tablename__ = "shopping_suggestion"
    __table_args__ = (
        CheckConstraint(
            "(product_id IS NULL) != (catalog_uuid IS NULL)", name="product_or_catalog_color"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("product.id"), index=True)
    # A catalog color's OFDB UUID, not a foreign key: a sync replaces the catalog.
    catalog_uuid: Mapped[str | None] = mapped_column(String(36))
    spools: Mapped[int]
    suggested_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    suggested_at: Mapped[datetime] = mapped_column(default=utcnow)
    status: Mapped[SuggestionStatus] = mapped_column(
        str_enum(SuggestionStatus, "suggestion_status"), default=SuggestionStatus.OPEN
    )
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    decided_at: Mapped[datetime | None]


class ShoppingHistory(Base):
    """One entry in a product's shopping list history. Entries are only ever added, never
    edited."""

    __tablename__ = "shopping_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), index=True)
    action: Mapped[ShoppingAction] = mapped_column(str_enum(ShoppingAction, "shopping_action"))
    # The spools or the size in grams the action concerned, if any.
    spools: Mapped[int | None]
    size_g: Mapped[int | None]
    # The item's on order once the action was done.
    on_order: Mapped[int]
    # None for the admin token or a machine token, which act for no user.
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    at: Mapped[datetime] = mapped_column(default=utcnow)

    user: Mapped[User | None] = relationship()


class PossibleDuplicate(Base):
    """A Review item: a product made by a scan that may be the same as one of its candidate
    "From the catalog" products."""

    __tablename__ = "possible_duplicate"

    id: Mapped[int] = mapped_column(primary_key=True)
    # The product the scan made.
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), index=True)
    state: Mapped[DuplicateState] = mapped_column(
        str_enum(DuplicateState, "duplicate_state"), default=DuplicateState.OPEN
    )
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    decided_at: Mapped[datetime | None]

    candidates: Mapped[list["DuplicateCandidate"]] = relationship(
        back_populates="duplicate", cascade="all, delete-orphan"
    )


class DuplicateCandidate(Base):
    """One "From the catalog" product a possible duplicate may be the same as."""

    __tablename__ = "possible_duplicate_candidate"
    __table_args__ = (UniqueConstraint("duplicate_id", "product_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    duplicate_id: Mapped[int] = mapped_column(ForeignKey("possible_duplicate.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), index=True)

    duplicate: Mapped[PossibleDuplicate] = relationship(back_populates="candidates")
