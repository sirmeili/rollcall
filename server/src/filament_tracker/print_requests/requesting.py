"""Uploading a model file, submitting and editing a request, and changing its priority
(ADR-0023).

Each action checks its gate and the request's own rules, then saves its change in one
transaction (`Core._saved`).
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from filament_tracker.auth import Principal
from filament_tracker.domain.enums import ModelFileKind, Priority
from filament_tracker.print_requests import notifications, service
from filament_tracker.print_requests.core import Core
from filament_tracker.print_requests.gates import Gate
from filament_tracker.print_requests.refused import Refused
from filament_tracker.print_requests.rules import RequestFields
from filament_tracker.print_requests.views import RequestDetail

NO_FILE = "this request has no file"


@dataclass(frozen=True)
class StoredModel:
    """A request's model file on disk, and the name to download it as."""

    path: Path
    name: str


@dataclass(frozen=True)
class ModelUpload:
    """A model file kept until a request is saved with it, by sending its id."""

    id: UUID
    name: str
    size: int
    kind: ModelFileKind


class Requesting(Core):
    async def upload_model(
        self, caller: Principal, name: str, body: AsyncIterator[bytes]
    ) -> ModelUpload:
        """Keep a Requester's 3MF or STL, read from `body` as it arrives, and commit; INVALID
        when it is neither. Whatever `body` raises (the client going away) is raised as is,
        with nothing kept."""
        user = self.check(caller, Gate.SUBMIT)
        kept = await self._parts.model_files.receive(
            self._session, user, name, body, self._parts.clock.now()
        )
        self._session.commit()
        return ModelUpload(id=kept.id, name=kept.file_name, size=kept.size, kind=kept.kind)

    def submit(self, caller: Principal, fields: RequestFields) -> RequestDetail:
        """A Requester's new request, Submitted. Editors and Admins are told of it."""
        user = self.check(caller, Gate.SUBMIT)
        clock = self._parts.clock
        created = service.submit(self._session, user, fields, today=clock.today(), now=clock.now())
        return self._saved(
            caller, created, self._notify(lambda: notifications.new_request(created))
        )

    def edit(self, caller: Principal, request_id: int, fields: RequestFields) -> RequestDetail:
        """The requester sends every field again, while the request is Submitted. A model
        file the edit replaced or removed is deleted once the edit is saved."""
        user = self.check(caller, Gate.EDIT)
        found = self._find(caller, request_id)
        files = self._parts.model_files
        clock = self._parts.clock
        saved = service.edit(
            self._session,
            found,
            user,
            fields,
            today=clock.today(),
            now=clock.now(),
            file_on_disk=files.exists(found.file_stored_name),
        )
        return self._saved(caller, found, lambda: files.delete(saved.old_file))

    def change_priority(
        self, caller: Principal, request_id: int, priority: Priority
    ) -> RequestDetail:
        """An Editor's or Admin's triage of an open request."""
        user = self.check(caller, Gate.PRIORITY)
        found = self._find(caller, request_id)
        service.change_priority(found, user, priority, now=self._parts.clock.now())
        return self._saved(caller, found)

    def model_file(self, caller: Principal, request_id: int) -> StoredModel:
        """The request's model file, to download; NOT_FOUND when it has none on disk."""
        self.check(caller, Gate.OPEN)
        found = self._find(caller, request_id)
        stored = found.file_stored_name
        if stored is None or not self._parts.model_files.exists(stored):
            raise Refused.not_found(NO_FILE)
        return StoredModel(self._parts.model_files.path(stored), found.file_name or "model")
