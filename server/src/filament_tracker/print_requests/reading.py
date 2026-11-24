"""Reading print requests: a request's detail, the Requests list and the Submitted count.
Reading never writes (ADR-0023)."""

from filament_tracker.auth import Principal
from filament_tracker.domain.enums import RequestStatus
from filament_tracker.print_requests import service
from filament_tracker.print_requests.core import Core
from filament_tracker.print_requests.gates import Gate
from filament_tracker.print_requests.read import ListFilter, Tab, visible_requests
from filament_tracker.print_requests.refused import Refused
from filament_tracker.print_requests.views import RequestDetail, RequestRow, row_of

NOT_OPEN = "Filter by open statuses only."


class Reading(Core):
    def detail(self, caller: Principal, request_id: int) -> RequestDetail:
        """The request as the caller sees it; NOT_FOUND for one they may not see."""
        self.check(caller, Gate.OPEN)
        return self._detail(caller, self._find(caller, request_id))

    def list(
        self,
        caller: Principal,
        tab: Tab = Tab.ACTIVE,
        statuses: list[RequestStatus] | None = None,
        mine: bool = False,
    ) -> list[RequestRow]:
        """Every request for Editors and Admins, otherwise the caller's own, in the tab's
        order. Editors and Admins may keep only some open statuses, or only their own."""
        self.check(caller, Gate.OPEN)
        statuses = statuses or []
        if any(s.closed for s in statuses):
            raise Refused.invalid({"status": NOT_OPEN})
        wanted = ListFilter(tab=tab, statuses=statuses, mine=mine)
        return [row_of(item) for item in visible_requests(self._session, caller, wanted)]

    def submitted_count(self, caller: Principal) -> int:
        """The Submitted requests, for the Requests link's count."""
        self.check(caller, Gate.COUNT)
        return service.submitted_count(self._session)
