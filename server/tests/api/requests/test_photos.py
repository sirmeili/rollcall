"""Photos of the finished print: an Admin adds them in the Done move or later, while the
request is Done or Picked Up; the requester sees them. Each is checked by its contents and
re-encoded, so no metadata survives."""

import io
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from api_helpers import CSRF
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from PIL import ExifTags, Image, PngImagePlugin
from request_helpers import REQUESTS, person, submitted
from sqlalchemy.orm import Session

from filament_tracker.db.request_models import PrintRequest, RequestPhoto
from filament_tracker.db.types import utcnow
from filament_tracker.domain.enums import RequestStatus, Role

PHOTO_UPLOADS = f"{REQUESTS}/photo-uploads"
TO_PRINTING = ["approved", "queued", "printing"]


def _exif(orientation: int = 1) -> Image.Exif:
    exif = Image.Exif()
    exif[ExifTags.Base.Make] = "Pocket Phone"
    exif[ExifTags.Base.Orientation] = orientation
    exif[ExifTags.Base.GPSInfo] = {
        ExifTags.GPS.GPSLatitudeRef: "N",
        ExifTags.GPS.GPSLatitude: (51.0, 30.0, 12.0),
    }
    return exif


def jpeg(size: tuple[int, int] = (40, 20), orientation: int = 1) -> bytes:
    """A real small JPEG carrying EXIF with a GPS position, and an ICC profile."""
    buffer = io.BytesIO()
    Image.new("RGB", size, (200, 30, 30)).save(
        buffer, "JPEG", exif=_exif(orientation), icc_profile=b"not really a profile"
    )
    return buffer.getvalue()


def png(size: tuple[int, int] = (40, 20), orientation: int = 1) -> bytes:
    """A real small PNG carrying EXIF with a GPS position, and a text chunk."""
    text = PngImagePlugin.PngInfo()
    text.add_text("Location", "51.5 N, 0.1 W")
    buffer = io.BytesIO()
    Image.new("RGBA", size, (30, 200, 30, 255)).save(
        buffer, "PNG", exif=_exif(orientation), pnginfo=text
    )
    return buffer.getvalue()


def upload_photo(user: TestClient, content: bytes, name: str = "print.jpg") -> Response:
    return user.post(
        PHOTO_UPLOADS,
        params={"name": name},
        content=content,
        headers={**CSRF, "Content-Type": "application/octet-stream"},
    )


def uploaded_photo(user: TestClient, content: bytes, name: str = "print.jpg") -> str:
    response = upload_photo(user, content, name)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def move(
    user: TestClient, request_id: int, from_status: str, to_status: str, **extra: Any
) -> Response:
    return user.post(
        f"{REQUESTS}/{request_id}/moves",
        json={"from_status": from_status, "to_status": to_status, **extra},
        headers=CSRF,
    )


def printing(sam: TestClient, frank: TestClient) -> int:
    """A request of sam's, moved on to Printing."""
    request_id = submitted(sam)["id"]
    at = "submitted"
    for to_status in TO_PRINTING:
        assert move(frank, request_id, at, to_status).status_code == 200
        at = to_status
    return request_id


def done(sam: TestClient, frank: TestClient, *photos: bytes) -> dict[str, Any]:
    """A request of sam's, moved to Done with these photos."""
    request_id = printing(sam, frank)
    ids = [uploaded_photo(frank, photo) for photo in photos]
    response = move(frank, request_id, "printing", "done", photo_ids=ids)
    assert response.status_code == 200, response.text
    return response.json()


def photo_url(request_id: int, photo_id: str) -> str:
    return f"{REQUESTS}/{request_id}/photos/{photo_id}"


def downloaded(user: TestClient, request_id: int, photo_id: str) -> Image.Image:
    response = user.get(photo_url(request_id, photo_id))
    assert response.status_code == 200, response.text
    image = Image.open(io.BytesIO(response.content))
    image.load()
    return image


@pytest.fixture
def sam(app: FastAPI, client: TestClient) -> TestClient:
    return person(app, "sam")


@pytest.fixture
def frank(app: FastAPI, client: TestClient) -> TestClient:
    return person(app, "frank", Role.ADMIN, requester=False)


def test_a_photo_added_in_the_done_move_reaches_the_requester_without_its_metadata(
    sam: TestClient, frank: TestClient
) -> None:
    moved = done(sam, frank, jpeg())

    [photo] = moved["photos"]
    image = downloaded(sam, moved["id"], photo["id"])
    assert image.format == "JPEG"
    assert dict(image.getexif()) == {}
    assert "icc_profile" not in image.info and "exif" not in image.info


def add_photos(user: TestClient, request_id: int, *ids: str) -> Response:
    return user.post(f"{REQUESTS}/{request_id}/photos", json={"photo_ids": list(ids)}, headers=CSRF)


def remove_photo(user: TestClient, request_id: int, photo_id: str) -> Response:
    return user.delete(photo_url(request_id, photo_id), headers=CSRF)


def _gif() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buffer, "GIF")
    return buffer.getvalue()


def test_a_png_keeps_its_format_and_loses_its_metadata(sam: TestClient, frank: TestClient) -> None:
    moved = done(sam, frank, png())

    [photo] = moved["photos"]
    response = sam.get(photo_url(moved["id"], photo["id"]))
    assert response.headers["content-type"] == "image/png"
    image = downloaded(sam, moved["id"], photo["id"])
    assert image.format == "PNG"
    assert dict(image.getexif()) == {}
    assert image.info == {}


@pytest.mark.parametrize("make", [jpeg, png], ids=["jpeg", "png"])
def test_the_orientation_is_applied_so_the_photo_is_not_sideways(
    sam: TestClient, frank: TestClient, make: Any
) -> None:
    # Orientation 6: the camera was turned, so the stored 40x20 pixels show as 20x40.
    moved = done(sam, frank, make(size=(40, 20), orientation=6))

    image = downloaded(sam, moved["id"], moved["photos"][0]["id"])
    assert image.size == (20, 40)


@pytest.mark.parametrize(
    "content",
    [
        b"just some text, renamed\n",
        b"<html><script>alert(1)</script></html>",
        _gif(),
        jpeg()[:200],
        b"",
    ],
    ids=["renamed-text", "html", "gif", "truncated-jpeg", "empty"],
)
def test_fakes_are_refused_by_their_contents_and_not_kept(
    frank: TestClient, files_dir: Path, content: bytes
) -> None:
    response = upload_photo(frank, content, "print.jpg")

    assert response.status_code == 422
    assert response.json()["detail"]["problems"]["photo"] == "That isn't a JPEG or PNG photo."
    assert not files_dir.exists() or list(files_dir.iterdir()) == []


def test_a_photo_over_40_megapixels_is_refused(frank: TestClient) -> None:
    buffer = io.BytesIO()
    Image.new("1", (6400, 6400)).save(buffer, "PNG")

    response = upload_photo(frank, buffer.getvalue(), "huge.png")

    assert response.status_code == 422
    assert "40 megapixels" in response.json()["detail"]["problems"]["photo"]


def test_a_photo_over_20_mb_is_refused(frank: TestClient) -> None:
    response = upload_photo(frank, jpeg() + b"\0" * (20 * 1024 * 1024), "big.jpg")

    assert response.status_code == 413


def test_the_file_name_is_cleaned_of_path_parts_and_unsafe_characters(frank: TestClient) -> None:
    response = upload_photo(frank, jpeg(), "..\\..\\Pictures/my <print>.jpg")

    assert response.json()["name"] == "my _print_.jpg"


def test_up_to_four_photos_and_no_fifth(sam: TestClient, frank: TestClient) -> None:
    moved = done(sam, frank, jpeg(), png(), jpeg(), png())
    assert len(moved["photos"]) == 4

    response = add_photos(frank, moved["id"], uploaded_photo(frank, jpeg()))

    assert response.status_code == 422
    assert "up to 4" in response.json()["detail"]["problems"]["photos"]


def test_an_admin_adds_photos_later_while_done_and_after_pick_up(
    sam: TestClient, frank: TestClient
) -> None:
    moved = done(sam, frank)
    later = add_photos(frank, moved["id"], uploaded_photo(frank, jpeg(), "front.jpg"))
    assert later.status_code == 200, later.text
    assert move(sam, moved["id"], "done", "picked_up").status_code == 200

    after = add_photos(frank, moved["id"], uploaded_photo(frank, png(), "side.png"))

    assert after.status_code == 200, after.text
    assert [p["name"] for p in after.json()["photos"]] == ["front.jpg", "side.png"]
    assert after.json()["can_change_photos"] is True


@pytest.mark.parametrize("status", ["submitted", "approved", "queued", "printing"])
def test_photos_are_not_added_outside_done_and_picked_up(
    sam: TestClient, frank: TestClient, status: str
) -> None:
    request_id = submitted(sam)["id"]
    at = "submitted"
    for to_status in TO_PRINTING[: ["submitted", *TO_PRINTING].index(status)]:
        assert move(frank, request_id, at, to_status).status_code == 200
        at = to_status

    response = add_photos(frank, request_id, uploaded_photo(frank, jpeg()))

    assert response.status_code == 422
    shown = frank.get(f"{REQUESTS}/{request_id}").json()
    assert (shown["status"], shown["photos"], shown["can_change_photos"]) == (status, [], False)


def test_only_the_done_move_takes_photos(sam: TestClient, frank: TestClient) -> None:
    request_id = printing(sam, frank)
    photo_id = uploaded_photo(frank, jpeg())

    response = move(frank, request_id, "printing", "failed", photo_ids=[photo_id])

    assert response.status_code == 422
    assert sam.get(f"{REQUESTS}/{request_id}").json()["status"] == "printing"


def test_a_refused_photo_leaves_the_done_move_unmade(
    app: FastAPI, sam: TestClient, frank: TestClient
) -> None:
    request_id = printing(sam, frank)
    someone_elses = uploaded_photo(person(app, "ada", Role.ADMIN), jpeg())

    response = move(frank, request_id, "printing", "done", photo_ids=[someone_elses])

    assert response.status_code == 422
    assert sam.get(f"{REQUESTS}/{request_id}").json()["status"] == "printing"


def test_an_upload_is_saved_with_one_request_only(sam: TestClient, frank: TestClient) -> None:
    photo_id = uploaded_photo(frank, jpeg())
    first = printing(sam, frank)
    second = printing(sam, frank)
    assert move(frank, first, "printing", "done", photo_ids=[photo_id]).status_code == 200

    response = move(frank, second, "printing", "done", photo_ids=[photo_id])

    assert response.status_code == 422


def test_removing_a_photo_deletes_its_files(
    sam: TestClient, frank: TestClient, files_dir: Path
) -> None:
    moved = done(sam, frank, jpeg(), png())
    kept, gone = moved["photos"]

    response = remove_photo(frank, moved["id"], gone["id"])

    assert response.status_code == 200, response.text
    assert [p["id"] for p in response.json()["photos"]] == [kept["id"]]
    assert sam.get(photo_url(moved["id"], gone["id"])).status_code == 404
    # The kept photo's full photo and email copy are all that is left.
    assert len(list(files_dir.iterdir())) == 2


def test_photos_are_not_removed_once_the_request_has_left_done_and_picked_up(
    sam: TestClient, frank: TestClient, db: Session
) -> None:
    moved = done(sam, frank, jpeg())
    found = db.get(PrintRequest, moved["id"])
    assert found is not None
    # No move leaves Done or Picked Up yet except Picked Up itself, so put it back by hand.
    found.status = RequestStatus.PRINTING
    db.commit()

    response = remove_photo(frank, moved["id"], moved["photos"][0]["id"])

    assert response.status_code == 422
    assert len(frank.get(f"{REQUESTS}/{moved['id']}").json()["photos"]) == 1


def test_adding_and_removing_write_history(sam: TestClient, frank: TestClient) -> None:
    moved = done(sam, frank)
    added = add_photos(frank, moved["id"], uploaded_photo(frank, jpeg(), "front.jpg")).json()

    removed = remove_photo(frank, moved["id"], added["photos"][0]["id"]).json()

    entries = [(e["kind"], e["username"], e["note"]) for e in removed["history"][:2]]
    assert entries == [
        ("photo_removed", "frank", "front.jpg"),
        ("photo_added", "frank", "front.jpg"),
    ]


def test_photos_added_in_the_done_move_follow_its_history_entry(
    sam: TestClient, frank: TestClient
) -> None:
    moved = done(sam, frank, jpeg())

    assert [e["kind"] for e in moved["history"][:2]] == ["photo_added", "status_changed"]


@pytest.mark.parametrize("who", ["requester", "editor"])
def test_only_admins_upload_add_and_remove_photos(
    app: FastAPI, sam: TestClient, frank: TestClient, who: str
) -> None:
    moved = done(sam, frank, jpeg())
    user = sam if who == "requester" else person(app, "eve", Role.EDITOR)
    photo_id = moved["photos"][0]["id"]

    assert upload_photo(user, jpeg()).status_code == 403
    assert add_photos(user, moved["id"], uploaded_photo(frank, jpeg())).status_code == 403
    assert remove_photo(user, moved["id"], photo_id).status_code == 403
    assert user.get(f"{REQUESTS}/{moved['id']}").json()["can_change_photos"] is False


def test_an_admin_who_asked_for_the_request_changes_its_photos(
    app: FastAPI, frank: TestClient
) -> None:
    ada = person(app, "ada", Role.ADMIN)
    moved = done(ada, frank)

    response = add_photos(ada, moved["id"], uploaded_photo(ada, jpeg()))

    assert response.status_code == 200, response.text


def test_photos_are_shown_to_everyone_who_sees_the_request(
    app: FastAPI, sam: TestClient, frank: TestClient
) -> None:
    moved = done(sam, frank, jpeg())
    editor = person(app, "eve", Role.EDITOR)
    other = person(app, "maya")
    photo_id = moved["photos"][0]["id"]

    assert editor.get(photo_url(moved["id"], photo_id)).status_code == 200
    assert other.get(photo_url(moved["id"], photo_id)).status_code == 404


def test_a_photo_is_served_only_under_its_own_request(sam: TestClient, frank: TestClient) -> None:
    moved = done(sam, frank, jpeg())
    other = done(sam, frank)

    response = sam.get(photo_url(other["id"], moved["photos"][0]["id"]))

    assert response.status_code == 404


def test_an_upload_never_saved_is_removed_after_a_day(
    sam: TestClient, frank: TestClient, db: Session, files_dir: Path
) -> None:
    stale = uploaded_photo(frank, jpeg())
    photo = db.get(RequestPhoto, UUID(stale))
    assert photo is not None
    photo.uploaded_at = utcnow() - timedelta(days=2)
    db.commit()

    uploaded_photo(frank, jpeg())

    request_id = printing(sam, frank)
    assert move(frank, request_id, "printing", "done", photo_ids=[stale]).status_code == 422
    assert len(list(files_dir.iterdir())) == 2
