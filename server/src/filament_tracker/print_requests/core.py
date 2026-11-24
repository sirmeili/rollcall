"""What every group of Print Requests actions shares: the session, the app's parts, the
gates, finding a request the caller may see, and saving a change."""

from collections.abc import Callable, Iterable
from typing import overload

from sqlalchemy.orm import Session

from filament_tracker.auth import Principal
from filament_tracker.db.models import User
from filament_tracker.db.request_models import PrintRequest
from filament_tracker.notifications.notification import Notification
from filament_tracker.print_requests.access import may_see
from filament_tracker.print_requests.gates import Gate, PersonGate, why_not
from filament_tracker.print_requests.parts import Parts
from filament_tracker.print_requests.refused import Refused
from filament_tracker.print_requests.views import RequestDetail, detail_of

NO_SUCH_REQUEST = "no such request"


class Core:
    """Bound to one database session: one per HTTP request."""

    def __init__(self, session: Session, parts: Parts) -> None:
        self._session = session
        self._parts = parts

    @overload
    def check(self, caller: Principal, gate: PersonGate) -> User: ...
    @overload
    def check(self, caller: Principal, gate: Gate) -> User | None: ...
    def check(self, caller: Principal, gate: Gate) -> User | None:
        """Refuse the caller (FORBIDDEN) unless they pass the gate; the user they act as,
        which a gate that lets only people through guarantees."""
        reason = why_not(self._session, caller, gate)
        if reason is not None:
            raise Refused.forbidden(reason)
        return caller.user

    def _find(self, caller: Principal, request_id: int) -> PrintRequest:
        """The request, or NOT_FOUND when there is none or the caller may not see it, so its
        existence isn't revealed."""
        found = self._session.get(PrintRequest, request_id)
        if found is None or not may_see(caller, found):
            raise Refused.not_found(NO_SUCH_REQUEST)
        return found

    def _detail(self, caller: Principal, request: PrintRequest) -> RequestDetail:
        return detail_of(self._session, self._parts, caller, request)

    def _saved(
        self,
        caller: Principal,
        request: PrintRequest,
        after: Callable[[], None] = lambda: None,
    ) -> RequestDetail:
        """Save a change (ADR-0023): commit, run `after`, the work that waits for the commit,
        then read the request again, with anything the commit wrote (the retry before it), and
        answer it as the caller sees it."""
        self._session.commit()
        after()
        self._session.refresh(request)
        return self._detail(caller, request)

    def _notify(self, build: Callable[[], Iterable[Notification]]) -> Callable[[], None]:
        """Work for after the commit: hand the notifications to the notifier."""
        return lambda: self._parts.notifier.send(self._session, build)
