"""Changing a request's holds by hand: a choice's grams, and adding, changing and removing
holds.

For signed-in Admins only; tokens are refused, since a change records who made it. Each
change names the status the caller saw the request in, and is refused STALE when it has moved
on, FORBIDDEN when the request isn't Approved, Waiting on Filament or Queued, and then
NOT_FOUND for a choice or hold that isn't the request's. Nothing is saved when it is refused,
and no email is sent. The retry the change sets off as it commits only checks the request
again; it holds no more for it.
"""

from collections.abc import Callable

from filament_tracker.auth import Principal
from filament_tracker.db.models import User
from filament_tracker.db.request_models import PrintRequest
from filament_tracker.domain.enums import RequestStatus
from filament_tracker.print_requests import filament
from filament_tracker.print_requests.core import Core
from filament_tracker.print_requests.gates import Gate
from filament_tracker.print_requests.views import RequestDetail


class ChangingHolds(Core):
    def set_grams(
        self,
        caller: Principal,
        request_id: int,
        choice_id: int,
        *,
        seen: RequestStatus,
        grams: int,
    ) -> RequestDetail:
        """Give a filament choice new grams, releasing its holds and holding them again."""
        return self._change_holds(
            caller,
            request_id,
            lambda found, user: filament.set_grams(
                self._session,
                found,
                choice_id,
                expected=seen,
                grams=grams,
                user=user,
                now=self._parts.clock.now(),
            ),
        )

    def add_hold(
        self,
        caller: Principal,
        request_id: int,
        choice_id: int,
        *,
        seen: RequestStatus,
        spool_id: int,
        grams: int,
    ) -> RequestDetail:
        """Hold grams of a Sealed or Open spool, of any product, for a filament choice: no
        more than the spool has available."""
        return self._change_holds(
            caller,
            request_id,
            lambda found, user: filament.add_hold(
                self._session,
                found,
                choice_id,
                expected=seen,
                spool_id=spool_id,
                grams=grams,
                user=user,
                now=self._parts.clock.now(),
            ),
        )

    def change_hold(
        self,
        caller: Principal,
        request_id: int,
        hold_id: int,
        *,
        seen: RequestStatus,
        spool_id: int,
        grams: int,
    ) -> RequestDetail:
        """Replace a hold with grams of a spool, the same one or another, releasing it."""
        return self._change_holds(
            caller,
            request_id,
            lambda found, user: filament.change_hold(
                self._session,
                found,
                hold_id,
                expected=seen,
                spool_id=spool_id,
                grams=grams,
                user=user,
                now=self._parts.clock.now(),
            ),
        )

    def remove_hold(
        self, caller: Principal, request_id: int, hold_id: int, *, seen: RequestStatus
    ) -> RequestDetail:
        """Release a hold."""
        return self._change_holds(
            caller,
            request_id,
            lambda found, user: filament.remove_hold(
                self._session,
                found,
                hold_id,
                expected=seen,
                user=user,
                now=self._parts.clock.now(),
            ),
        )

    def _change_holds(
        self,
        caller: Principal,
        request_id: int,
        change: Callable[[PrintRequest, User], None],
    ) -> RequestDetail:
        """Check the caller may change the request's holds, make the change and commit it;
        the request as the caller sees it after."""
        user = self.check(caller, Gate.HOLDS)
        found = self._find(caller, request_id)
        change(found, user)
        return self._saved(caller, found)
