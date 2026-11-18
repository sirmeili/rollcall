"""The Print Requests module's tables: print requests, their filament choices, their request
history, and model files uploaded but not yet saved with a request.

Print Requests depends on Inventory and the catalog, never the reverse (ADR-0014): these
tables refer to users and products, and nothing in Inventory refers to them. A catalog
color is kept by its OFDB UUID, as catalog links are (ADR-0016).
"""

import uuid
from datetime import date, datetime

from sqlalchemy import JSON, CheckConstraint, Date, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from filament_tracker.db.models import Base, Product, User
from filament_tracker.db.types import str_enum, utcnow
from filament_tracker.domain.enums import HistoryKind, ModelFileKind, Priority, RequestStatus

TITLE_MAX = 120
NOTES_MAX = 2000
LINK_MAX = 2000
CHOICE_NOTE_MAX = 80
FILE_NAME_MAX = 255


class PrintRequest(Base):
    """A Requester's ask to have something printed. Its model is a file, a link or both, or
    else its notes say where the model is.

    The model file, if any, lives in the request-files directory under `file_stored_name`,
    a random name; `file_name` is the uploader's name for it, cleaned of path parts."""

    __tablename__ = "print_request"

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    title: Mapped[str] = mapped_column(String(TITLE_MAX))
    notes: Mapped[str] = mapped_column(String(NOTES_MAX), default="")
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    needed_by: Mapped[date | None] = mapped_column(Date)
    priority: Mapped[Priority] = mapped_column(str_enum(Priority, "request_priority"))
    link: Mapped[str | None] = mapped_column(String(LINK_MAX))
    status: Mapped[RequestStatus] = mapped_column(str_enum(RequestStatus, "request_status"))
    file_stored_name: Mapped[str | None] = mapped_column(String(64))
    file_name: Mapped[str | None] = mapped_column(String(FILE_NAME_MAX))
    file_size: Mapped[int | None]
    file_sha256: Mapped[str | None] = mapped_column(String(64))
    file_kind: Mapped[ModelFileKind | None] = mapped_column(
        str_enum(ModelFileKind, "model_file_kind")
    )
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)

    requester: Mapped[User] = relationship()
    choices: Mapped[list["FilamentChoice"]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
        order_by="FilamentChoice.position",
    )
    history: Mapped[list["RequestHistory"]] = relationship(
        back_populates="request", order_by="RequestHistory.id"
    )


class FilamentChoice(Base):
    """One filament a request asks for: a product or a catalog color, never both. A catalog
    color's line, name and colors are noted when chosen, so one the catalog later drops can
    still say what it was."""

    __tablename__ = "filament_choice"
    __table_args__ = (
        CheckConstraint(
            "(product_id IS NULL) <> (catalog_uuid IS NULL)", name="product_or_catalog_color"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("print_request.id"), index=True)
    position: Mapped[int]
    product_id: Mapped[int | None] = mapped_column(ForeignKey("product.id"))
    catalog_uuid: Mapped[str | None] = mapped_column(String(36))
    catalog_line: Mapped[str | None] = mapped_column(String(200))
    catalog_name: Mapped[str | None] = mapped_column(String(200))
    catalog_hexes: Mapped[list[str] | None] = mapped_column(JSON)
    note: Mapped[str] = mapped_column(String(CHOICE_NOTE_MAX), default="")

    request: Mapped[PrintRequest] = relationship(back_populates="choices")
    product: Mapped[Product | None] = relationship()


class RequestHistory(Base):
    """One entry in a request's history. Entries are only ever added, never edited."""

    __tablename__ = "request_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("print_request.id"), index=True)
    kind: Mapped[HistoryKind] = mapped_column(str_enum(HistoryKind, "request_history_kind"))
    # None for the admin token or a machine token, which act for no user.
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    at: Mapped[datetime] = mapped_column(default=utcnow)
    # An edit's changed fields.
    fields: Mapped[list[str] | None] = mapped_column(JSON)
    # A priority change's old and new values.
    from_value: Mapped[str | None] = mapped_column(String(32))
    to_value: Mapped[str | None] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(String(500))

    request: Mapped[PrintRequest] = relationship(back_populates="history")
    user: Mapped[User | None] = relationship()


class RequestUpload(Base):
    """A model file uploaded by a Requester and checked, waiting to be saved with a request.
    Saving it moves its details onto the request and removes this row."""

    __tablename__ = "request_upload"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    stored_name: Mapped[str] = mapped_column(String(64), unique=True)
    file_name: Mapped[str] = mapped_column(String(FILE_NAME_MAX))
    size: Mapped[int]
    sha256: Mapped[str] = mapped_column(String(64))
    kind: Mapped[ModelFileKind] = mapped_column(str_enum(ModelFileKind, "upload_file_kind"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
