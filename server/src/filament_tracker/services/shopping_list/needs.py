"""What print requests are short of: the request-needs reader.

Inventory never imports Print Requests (ADR-0014), so the app wires in a reader at start
(`api/request_needs.py`) that answers each product's holding requests' shorts, asked for the
viewing user (ADR-0020). It decides which requests that user may see named.
"""

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from filament_tracker.auth import Principal


@dataclass(frozen=True)
class RequestShort:
    """A print request holding filament that is short of a product."""

    request_id: int
    # None when the viewing user may not see the request: it reads "a print request".
    title: str | None
    short_g: int


class RequestNeedsReader(Protocol):
    def __call__(self, session: Session, viewer: Principal) -> dict[int, list[RequestShort]]:
        """Each product's requests short of it, by product ID, in Active-tab order."""
        ...
