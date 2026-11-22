"""Resolve Review items and bring them back (Editor and up). Undo uses
`/events/{id}/revert`. A possible duplicate is resolved by Same product, which cannot be
brought back, or Keep separate, which can."""

from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from filament_tracker.api.read_schemas import EventOut
from filament_tracker.api.views import event_out
from filament_tracker.api.write_schemas import SameProductIn
from filament_tracker.auth import DbSession, Editor, Principal
from filament_tracker.db.models import Event
from filament_tracker.db.types import utcnow
from filament_tracker.services import edits
from filament_tracker.services.shopping_list import duplicates

router = APIRouter(prefix="/review", tags=["review"])


def _event(session: DbSession, event_id: UUID) -> Event:
    event = session.get(Event, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such event")
    return event


@router.post("/events/{event_id}/accept", response_model=EventOut)
def accept(event_id: UUID, caller: Editor, session: DbSession) -> EventOut:
    """The flagged event was right: keep it and take it out of Review."""
    event = _event(session, event_id)
    try:
        edits.accept_event(event, utcnow(), user_id=caller.user.id if caller.user else None)
    except edits.EditError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    session.commit()
    session.refresh(event)
    return event_out(event)


@router.post("/events/{event_id}/unaccept", response_model=EventOut)
def unaccept(event_id: UUID, _: Editor, session: DbSession) -> EventOut:
    """Bring back: return an accepted flagged event to Review."""
    event = _event(session, event_id)
    try:
        edits.unaccept_event(event)
    except edits.EditError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    session.commit()
    session.refresh(event)
    return event_out(event)


def _change(session: DbSession, change: Callable[[], object]) -> Response:
    try:
        change()
    except edits.NotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except edits.EditError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except duplicates.NoSuchDuplicate as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such possible duplicate") from exc
    except duplicates.DuplicateDecided as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "the possible duplicate was already decided"
        ) from exc
    except duplicates.NotACandidate as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "that product is not one of its candidates"
        ) from exc
    except duplicates.CandidateHasSpools as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "that product has spools, so it cannot be merged"
        ) from exc
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/tags/{uid}/restore", status_code=status.HTTP_204_NO_CONTENT)
def restore(uid: str, _: Editor, session: DbSession) -> Response:
    """Bring back: show a dismissed unidentified tag in Review again."""
    return _change(session, lambda: edits.restore_tag(session, uid))


@router.post("/tags/{uid}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss(uid: str, _: Editor, session: DbSession) -> Response:
    """Hide an unidentified tag from Review."""
    return _change(session, lambda: edits.dismiss_tag(session, uid, utcnow()))


@router.post("/spools/{spool_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_likely_empty(spool_id: int, _: Editor, session: DbSession) -> Response:
    """Hide a spool's "Likely empty" suggestion; the spool stays open."""
    return _change(session, lambda: edits.dismiss_likely_empty(session, spool_id, utcnow()))


@router.post("/spools/{spool_id}/restore", status_code=status.HTTP_204_NO_CONTENT)
def restore_likely_empty(spool_id: int, _: Editor, session: DbSession) -> Response:
    """Bring back: show a dismissed "Likely empty" suggestion again."""
    return _change(session, lambda: edits.restore_likely_empty(session, spool_id))


def _user_id(caller: Principal) -> int | None:
    return caller.user.id if caller.user else None


@router.post("/duplicates/{duplicate_id}/same-product", status_code=status.HTTP_204_NO_CONTENT)
def same_product(
    duplicate_id: int, body: SameProductIn, caller: Editor, session: DbSession
) -> Response:
    """The scanned product is this candidate: merge the candidate into it and delete it."""
    return _change(
        session,
        lambda: duplicates.same_product(
            session, duplicate_id, body.candidate_id, _user_id(caller), utcnow()
        ),
    )


@router.post("/duplicates/{duplicate_id}/keep-separate", status_code=status.HTTP_204_NO_CONTENT)
def keep_separate(duplicate_id: int, caller: Editor, session: DbSession) -> Response:
    """They are different products: leave both, and take it out of Review."""
    return _change(
        session,
        lambda: duplicates.keep_separate(session, duplicate_id, _user_id(caller), utcnow()),
    )


@router.post("/duplicates/{duplicate_id}/restore", status_code=status.HTTP_204_NO_CONTENT)
def restore_duplicate(duplicate_id: int, _: Editor, session: DbSession) -> Response:
    """Bring back: return a possible duplicate kept separate to Review."""
    return _change(session, lambda: duplicates.bring_back(session, duplicate_id))
