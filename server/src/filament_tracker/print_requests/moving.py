"""Moving a request along the pipeline, and adding and removing photos of its print.

Each action is one transaction (ADR-0023): it checks, changes and commits, then hands the
notifications to the notifier and deletes a removed photo's files, and answers the request
as the caller sees it after the commit, with any move the retry made before it.
"""

from collections.abc import Callable, Iterable
from uuid import UUID

from filament_tracker.auth import Principal
from filament_tracker.db.request_models import PrintRequest, RequestPhoto
from filament_tracker.domain.enums import RequestStatus
from filament_tracker.notifications.notification import Notification
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
        self.check(caller, Gate.MOVE)
        found = self._find(caller, request_id)
        now = self._parts.clock.now()
        moved = filament.make_move(
            self._session,
            found,
            expected=from_status,
            to_status=to_status,
            grams=grams or {},
            movers=movers(caller, found),
            user=caller.user,
            note=note,
            now=now,
        )
        added: list[RequestPhoto] = []
        if photo_ids:
            if not moved.move.photos:
                raise Refused.invalid({photos.PHOTOS: NO_PHOTOS})
            added = photos.add(self._session, found, photo_ids, caller.user, now)
        return self._saved(
            caller,
            found,
            lambda: notifications.request_moved(moved, *self._copies(added)),
        )

    def _copies(self, added: list[RequestPhoto]) -> tuple[list[bytes], UUID | None]:
        """The email copies of the added photos, and the first one's id."""
        return self._parts.photos.email_copies(added), added[0].id if added else None

    def _saved(
        self,
        caller: Principal,
        request: PrintRequest,
        build: Callable[[], Iterable[Notification]],
    ) -> RequestDetail:
        """Commit, hand the notifications to the notifier, and read the request back."""
        self._session.commit()
        self._parts.notifier.send(self._session, build)
        return self._detail(caller, request)
