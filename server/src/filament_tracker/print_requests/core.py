"""What every group of Print Requests actions shares: the session, the app's parts, the
gates, and finding a request the caller may see."""

from sqlalchemy.orm import Session

from filament_tracker.auth import Principal
from filament_tracker.db.request_models import PrintRequest
from filament_tracker.print_requests.access import may_see
from filament_tracker.print_requests.gates import Gate, why_not
from filament_tracker.print_requests.parts import Parts
from filament_tracker.print_requests.refused import Refused
from filament_tracker.print_requests.views import RequestDetail, detail_of

NO_SUCH_REQUEST = "no such request"


class Core:
    """Bound to one database session: one per HTTP request."""

    def __init__(self, session: Session, parts: Parts) -> None:
        self._session = session
        self._parts = parts

    def may(self, caller: Principal, gate: Gate) -> bool:
        """Whether the caller passes the gate, before anything they sent is looked at."""
        return why_not(self._session, caller, gate) is None

    def check(self, caller: Principal, gate: Gate) -> None:
        """Refuse the caller (FORBIDDEN) unless they pass the gate."""
        reason = why_not(self._session, caller, gate)
        if reason is not None:
            raise Refused.forbidden(reason)

    def _find(self, caller: Principal, request_id: int) -> PrintRequest:
        """The request, or NOT_FOUND when there is none or the caller may not see it, so its
        existence isn't revealed."""
        found = self._session.get(PrintRequest, request_id)
        if found is None or not may_see(caller, found):
            raise Refused.not_found(NO_SUCH_REQUEST)
        return found

    def _detail(self, caller: Principal, request: PrintRequest) -> RequestDetail:
        return detail_of(self._session, self._parts, caller, request)
