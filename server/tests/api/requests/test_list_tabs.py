"""The Requests list's Active and Closed tabs, its status filter and Only mine."""

from datetime import UTC, datetime, timedelta

from api_helpers import signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient
from request_helpers import REQUESTS, person, submitted
from sqlalchemy.orm import Session

from filament_tracker.db.request_models import PrintRequest, RequestHistory
from filament_tracker.domain.enums import HistoryKind, RequestStatus, Role

START = datetime(2026, 11, 1, 12, tzinfo=UTC)


def _moved(db: Session, request_id: int, to: str, *, hours: int = 0) -> None:
    """Put the request in a status as a move made `hours` after START would."""
    found = db.get(PrintRequest, request_id)
    assert found is not None
    found.history.append(
        RequestHistory(
            kind=HistoryKind.STATUS_CHANGED,
            at=START + timedelta(hours=hours),
            from_value=found.status.value,
            to_value=to,
        )
    )
    found.status = RequestStatus(to)
    db.commit()


def _ids(user: TestClient, query: str = "") -> list[int]:
    response = user.get(f"{REQUESTS}{query}")
    assert response.status_code == 200, response.text
    return [r["id"] for r in response.json()]


def test_the_active_tab_holds_every_open_status_and_is_the_default(
    app: FastAPI, client: TestClient, db: Session
) -> None:
    sam = person(app, "sam")
    open_ids = []
    for status in RequestStatus:
        created = submitted(sam, title=status.value)
        if status is not RequestStatus.SUBMITTED:
            _moved(db, created["id"], status.value)
        if not status.closed:
            open_ids.append(created["id"])
    editor = signed_in(app, Role.EDITOR)

    assert sorted(_ids(editor)) == sorted(open_ids)
    assert sorted(_ids(editor, "?tab=active")) == sorted(open_ids)
    assert len(open_ids) == 7


def test_the_closed_tab_holds_picked_up_rejected_and_cancelled_newest_move_first(
    app: FastAPI, client: TestClient, db: Session
) -> None:
    sam = person(app, "sam")
    ids = {name: submitted(sam, title=name)["id"] for name in ("old", "new", "mid", "open")}
    _moved(db, ids["old"], "rejected", hours=1)
    _moved(db, ids["mid"], "approved", hours=2)
    _moved(db, ids["mid"], "cancelled", hours=5)
    _moved(db, ids["new"], "approved", hours=3)
    _moved(db, ids["new"], "done", hours=4)
    _moved(db, ids["new"], "picked_up", hours=9)
    _moved(db, ids["open"], "approved", hours=20)

    rows = signed_in(app, Role.ADMIN).get(f"{REQUESTS}?tab=closed").json()

    assert [r["id"] for r in rows] == [ids["new"], ids["mid"], ids["old"]]
    assert [r["status"] for r in rows] == ["picked_up", "cancelled", "rejected"]


def test_the_active_tab_keeps_the_most_pressing_first(
    app: FastAPI, client: TestClient, db: Session
) -> None:
    sam = person(app, "sam")
    normal = submitted(sam)["id"]
    urgent_queued = submitted(sam, priority="urgent")["id"]
    _moved(db, urgent_queued, "queued")

    assert _ids(signed_in(app, Role.EDITOR)) == [urgent_queued, normal]


def test_an_unknown_tab_is_refused(app: FastAPI, client: TestClient) -> None:
    assert signed_in(app, Role.EDITOR).get(f"{REQUESTS}?tab=all").status_code == 422


def test_editors_and_admins_keep_only_the_statuses_they_pick(
    app: FastAPI, client: TestClient, db: Session
) -> None:
    sam = person(app, "sam")
    waiting = submitted(sam)["id"]
    queued = submitted(sam, priority="urgent")["id"]
    failed = submitted(sam)["id"]
    _moved(db, queued, "queued")
    _moved(db, failed, "failed")

    for role in (Role.EDITOR, Role.ADMIN):
        user = signed_in(app, role)
        assert _ids(user, "?status=queued") == [queued]
        assert _ids(user, "?status=queued&status=submitted") == [queued, waiting]
        assert _ids(user, "?status=failed&tab=active") == [failed]


def test_the_status_filter_takes_only_open_statuses(app: FastAPI, client: TestClient) -> None:
    editor = signed_in(app, Role.EDITOR)

    response = editor.get(f"{REQUESTS}?status=rejected")

    assert response.status_code == 422
    assert response.json()["detail"]["problems"] == {"status": "Filter by open statuses only."}
    assert editor.get(f"{REQUESTS}?status=lost").status_code == 422


def test_only_mine_keeps_the_callers_own_requests_on_both_tabs(
    app: FastAPI, client: TestClient, db: Session
) -> None:
    dana = person(app, "dana", Role.EDITOR)
    sam = person(app, "sam")
    hers = submitted(dana)["id"]
    hers_closed = submitted(dana)["id"]
    submitted(sam)
    theirs_closed = submitted(sam)["id"]
    _moved(db, hers_closed, "rejected", hours=1)
    _moved(db, theirs_closed, "rejected", hours=2)

    assert _ids(dana, "?mine=true") == [hers]
    assert _ids(dana, "?tab=closed&mine=true") == [hers_closed]
    assert _ids(dana, "?tab=closed") == [theirs_closed, hers_closed]


def test_a_requester_sees_only_their_own_on_both_tabs_whatever_they_ask(
    app: FastAPI, client: TestClient, db: Session
) -> None:
    sam, maya = person(app, "sam"), person(app, "maya")
    mine = submitted(sam)["id"]
    mine_closed = submitted(sam)["id"]
    theirs = submitted(maya)["id"]
    theirs_closed = submitted(maya)["id"]
    _moved(db, mine_closed, "cancelled")
    _moved(db, theirs_closed, "cancelled")
    _moved(db, theirs, "queued")

    assert _ids(sam) == [mine]
    assert _ids(sam, "?tab=closed") == [mine_closed]
    assert _ids(sam, "?status=queued") == [mine]
    assert _ids(sam, "?mine=false") == [mine]
    assert _ids(sam, "?tab=closed&mine=false") == [mine_closed]


def test_the_requests_link_still_counts_only_submitted_requests(
    app: FastAPI, client: TestClient, db: Session
) -> None:
    sam = person(app, "sam")
    submitted(sam)
    _moved(db, submitted(sam)["id"], "queued")
    _moved(db, submitted(sam)["id"], "rejected")

    assert signed_in(app, Role.EDITOR).get(f"{REQUESTS}/count").json() == {"submitted": 1}
