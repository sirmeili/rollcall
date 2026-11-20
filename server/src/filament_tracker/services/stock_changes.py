"""Stock changes: Inventory notes that its stock changed, and anything outside Inventory may
react before the change is committed (ADR-0020).

Inventory calls `changed` wherever grams may have come or gone: a spool event or its undo,
a new grams left from the AMS or by hand, a catalog link changing, or a hold released. It
names no one who reacts, so it never imports Print Requests (ADR-0014). The app wires a
reaction to its sessions with `on_change`, and it runs once, in the same session and
transaction, just before a commit that follows a change: whichever thread the session is in.
"""

from collections.abc import Callable

from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker

_CHANGED = "stock_changed"


def changed(session: Session) -> None:
    """Note that this session changed stock."""
    session.info[_CHANGED] = True


def on_change(sessions: sessionmaker[Session], react: Callable[[Session], None]) -> None:
    """Run `react` before each commit of these sessions that follows a stock change."""

    @event.listens_for(sessions, "before_commit")
    def _react(session: Session) -> None:
        if session.info.pop(_CHANGED, False):
            react(session)
