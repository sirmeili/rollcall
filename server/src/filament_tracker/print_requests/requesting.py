"""Submitting and editing a request, and changing its priority (ADR-0023).

Each action checks its gate and the request's own rules, commits one transaction, then runs
the work that must wait for the commit, and returns the caller's view of the request read
after it.
"""

from dataclasses import dataclass

from filament_tracker.auth import Principal
from filament_tracker.domain.enums import Priority
from filament_tracker.print_requests import notifications, service
from filament_tracker.print_requests.core import Core
from filament_tracker.print_requests.gates import Gate
from filament_tracker.print_requests.refused import Refused
from filament_tracker.print_requests.rules import RequestFields
from filament_tracker.print_requests.views import RequestDetail

NO_FILE = "this request has no file"


@dataclass(frozen=True)
class StoredModel:
    """A request's model file on disk: its stored name, and the name to download it as."""

    stored_name: str
    name: str


class Requesting(Core):
    def submit(self, caller: Principal, fields: RequestFields) -> RequestDetail:
        """A Requester's new request, Submitted. Editors and Admins are told of it."""
        self.check(caller, Gate.SUBMIT)
        assert caller.user is not None  # noqa: S101 - the gate lets only people through
        clock = self._parts.clock
        created = service.submit(
            self._session, caller.user, fields, today=clock.today(), now=clock.now()
        )
        self._session.commit()
        self._parts.notifier.send(self._session, lambda: notifications.new_request(created))
        return self._detail(caller, created)

    def edit(self, caller: Principal, request_id: int, fields: RequestFields) -> RequestDetail:
        """The requester sends every field again, while the request is Submitted. A model
        file the edit replaced or removed is deleted once the edit is saved."""
        self.check(caller, Gate.EDIT)
        assert caller.user is not None  # noqa: S101 - the gate lets only people through
        found = self._find(caller, request_id)
        files = self._parts.model_files
        clock = self._parts.clock
        saved = service.edit(
            self._session,
            found,
            caller.user,
            fields,
            today=clock.today(),
            now=clock.now(),
            file_on_disk=files.exists(found.file_stored_name),
        )
        self._session.commit()
        files.delete(saved.old_file)
        return self._detail(caller, found)

    def change_priority(
        self, caller: Principal, request_id: int, priority: Priority
    ) -> RequestDetail:
        """An Editor's or Admin's triage of an open request."""
        self.check(caller, Gate.PRIORITY)
        found = self._find(caller, request_id)
        service.change_priority(found, caller.user, priority, now=self._parts.clock.now())
        self._session.commit()
        return self._detail(caller, found)

    def model_file(self, caller: Principal, request_id: int) -> StoredModel:
        """The request's model file, to download; NOT_FOUND when it has none on disk."""
        self.check(caller, Gate.OPEN)
        found = self._find(caller, request_id)
        stored = found.file_stored_name
        if stored is None or not self._parts.model_files.exists(stored):
            raise Refused.not_found(NO_FILE)
        return StoredModel(stored, found.file_name or "model")
