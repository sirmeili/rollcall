"""Moving a request along the pipeline, with photos of its print in a move that takes them
(Done).

Each move is one transaction (ADR-0023): once it has committed, the notifications go to the
notifier, and the request is answered as the caller sees it, with any move the retry made
before the commit.
"""

from uuid import UUID

from filament_tracker.auth import Principal
from filament_tracker.db.request_models import RequestPhoto
from filament_tracker.domain.enums import RequestStatus
from filament_tracker.print_requests import filament, notifications, photos
from filament_tracker.print_requests.access import movers
from filament_tracker.print_requests.core import Core
from filament_tracker.print_requests.gates import Gate
from filament_tracker.print_requests.refused import Refused
from filament_tracker.print_requests.views import RequestDetail

NO_PHOTOS = "Photos can be added only when moving a request to Done."


class Moving(Core):
    def move(
        self,
        caller: Principal,
        request_id: int,
        from_status: RequestStatus,
        to_status: RequestStatus,
        grams: dict[int, int] | None = None,
        note: str = "",
        photo_ids: list[UUID] | None = None,
    ) -> RequestDetail:
        """Move the request from the status the caller saw it in, saving any photo uploads
        with a move that takes them (Done). STALE when it has moved on, FORBIDDEN when the
        pipeline has no such move for the caller."""
        user = self.check(caller, Gate.MOVE)
        found = self._find(caller, request_id)
        now = self._parts.clock.now()
        moved = filament.make_move(
            self._session,
            found,
            expected=from_status,
            to_status=to_status,
            grams=grams or {},
            movers=movers(caller, found),
            user=user,
            note=note,
            now=now,
        )
        added: list[RequestPhoto] = []
        if photo_ids:
            if not moved.move.photos:
                raise Refused.invalid({photos.PHOTOS: NO_PHOTOS})
            added = photos.add(self._session, found, photo_ids, user, now)
        copies = self._parts.photos.email_copies
        return self._saved(
            caller,
            found,
            self._notify(lambda: notifications.request_moved(moved, *copies(added))),
        )
