"""Model files: uploading a 3MF or STL, saving it with a request, replacing, removing and
downloading it."""

import io
import struct
import zipfile
from pathlib import Path
from typing import Any

import pytest
from api_helpers import CSRF, admin, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient
from request_helpers import REQUESTS, edit, person, submit, submitted

from filament_tracker.domain.enums import Role

UPLOADS = f"{REQUESTS}/uploads"


def three_mf(*, with_model: bool = True) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        if with_model:
            archive.writestr("3D/3dmodel.model", "<model/>")
    return buffer.getvalue()


def binary_stl(triangles: int = 2, header: bytes = b"solid but binary") -> bytes:
    # By default a header that starts with "solid", as some exporters write.
    header = header.ljust(80, b" ")
    return header + struct.pack("<I", triangles) + b"\0" * 50 * triangles


ASCII_STL = b"solid cube\n  facet normal 0 0 1\n  endfacet\nendsolid cube\n"


def upload(user: TestClient, content: bytes, name: str = "model.3mf") -> Any:
    return user.post(
        UPLOADS,
        params={"name": name},
        content=content,
        headers={**CSRF, "Content-Type": "application/octet-stream"},
    )


def uploaded(user: TestClient, content: bytes, name: str = "model.3mf") -> dict[str, Any]:
    response = upload(user, content, name)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def sam(app: FastAPI, client: TestClient) -> TestClient:
    return person(app, "sam")


@pytest.mark.parametrize(
    ("content", "kind"),
    [(three_mf(), "3mf"), (binary_stl(), "stl"), (ASCII_STL, "stl")],
    ids=["3mf", "binary-stl", "ascii-stl"],
)
def test_3mf_and_stl_files_are_accepted(sam: TestClient, content: bytes, kind: str) -> None:
    found = uploaded(sam, content, "part.bin")

    assert (found["kind"], found["size"]) == (kind, len(content))


@pytest.mark.parametrize(
    ("content", "name"),
    [
        (three_mf(with_model=False), "model.3mf"),
        (b"just some text, renamed\n", "notes.stl"),
        (binary_stl(header=b"exported")[:-7], "cut-short.stl"),
        (b"", "empty.stl"),
    ],
    ids=["3mf-without-model", "renamed-text", "truncated-binary-stl", "empty"],
)
def test_other_files_are_refused_by_their_contents(
    sam: TestClient, content: bytes, name: str
) -> None:
    response = upload(sam, content, name)

    assert response.status_code == 422
    assert "3MF or STL" in response.json()["detail"]["problems"]["file"]


def test_a_refused_file_is_not_kept(sam: TestClient, files_dir: Path) -> None:
    upload(sam, b"not a model", "x.stl")

    assert list(files_dir.iterdir()) == []


def test_the_file_name_is_cleaned_of_path_parts_and_unsafe_characters(sam: TestClient) -> None:
    found = uploaded(sam, three_mf(), '..\\..\\Desktop/évil<"name">.3mf')

    assert found["name"] == "évil__name__.3mf"


def test_a_file_saved_with_a_request_counts_as_its_model(sam: TestClient) -> None:
    file = uploaded(sam, three_mf(), "lamp.3mf")

    created = submitted(sam, upload_id=file["id"], link=None, notes="")

    assert created["file"] == {
        "name": "lamp.3mf",
        "size": file["size"],
        "kind": "3mf",
        "missing": False,
    }
    assert sam.get(REQUESTS).json()[0]["model"] == "file"


def test_someone_elses_upload_cannot_be_used(app: FastAPI, sam: TestClient) -> None:
    file = uploaded(person(app, "maya"), three_mf())

    response = submit(sam, upload_id=file["id"])

    assert "file" in response.json()["detail"]["problems"]


def test_an_upload_is_saved_with_one_request_only(sam: TestClient) -> None:
    file = uploaded(sam, three_mf())
    submitted(sam, upload_id=file["id"])

    assert submit(sam, upload_id=file["id"]).status_code == 422


def test_only_requesters_upload(app: FastAPI, client: TestClient) -> None:
    viewer = person(app, "theo", requester=False)
    editor = signed_in(app, Role.EDITOR)

    assert upload(viewer, three_mf()).status_code == 403
    assert upload(editor, three_mf()).status_code == 403
    assert client.post(UPLOADS, content=three_mf(), headers=admin()).status_code == 403


def test_replacing_the_file_deletes_the_old_one(sam: TestClient, files_dir: Path) -> None:
    first = uploaded(sam, three_mf(), "v1.3mf")
    created = submitted(sam, upload_id=first["id"])
    second = uploaded(sam, binary_stl(), "v2.stl")

    response = edit(sam, created["id"], upload_id=second["id"])

    assert response.json()["file"]["name"] == "v2.stl"
    assert response.json()["history"][0]["fields"] == ["file"]
    assert len(list(files_dir.iterdir())) == 1
    download = sam.get(f"{REQUESTS}/{created['id']}/file")
    assert download.content == binary_stl()


def test_a_refused_edit_keeps_the_old_file(sam: TestClient) -> None:
    first = uploaded(sam, three_mf(), "v1.3mf")
    created = submitted(sam, upload_id=first["id"])
    second = uploaded(sam, binary_stl(), "v2.stl")

    response = edit(sam, created["id"], upload_id=second["id"], needed_by="2000-01-01")

    assert response.status_code == 422, response.text
    download = sam.get(f"{REQUESTS}/{created['id']}/file")
    assert download.content == three_mf()


def test_removing_the_file(sam: TestClient, files_dir: Path) -> None:
    file = uploaded(sam, three_mf())
    created = submitted(sam, upload_id=file["id"])

    body = {"remove_file": True}
    response = sam.patch(
        f"{REQUESTS}/{created['id']}",
        json={**_body_of(created), **body},
        headers=CSRF,
    )

    assert response.status_code == 200, response.text
    assert response.json()["file"] is None
    assert response.json()["history"][0]["fields"] == ["file"]
    assert list(files_dir.iterdir()) == []


def test_removing_the_only_model_needs_a_link_or_notes(sam: TestClient) -> None:
    file = uploaded(sam, three_mf())
    created = submitted(sam, upload_id=file["id"], link=None)

    response = sam.patch(
        f"{REQUESTS}/{created['id']}",
        json={**_body_of(created), "remove_file": True},
        headers=CSRF,
    )

    assert "notes" in response.json()["detail"]["problems"]


def _body_of(read: dict[str, Any]) -> dict[str, Any]:
    """An edit body that sends a request's fields back unchanged."""
    return {
        "title": read["title"],
        "notes": read["notes"],
        "quantity": read["quantity"],
        "needed_by": read["needed_by"],
        "priority": read["priority"],
        "link": read["link"],
        "choices": [
            {"catalog_color": c["catalog_color"], "note": c["note"]}
            if c["kind"] == "catalog_color"
            else {"product_id": c["product_id"], "note": c["note"]}
            for c in read["choices"]
        ],
    }


# --- Downloads -----------------------------------------------------------------------------


def test_a_download_always_saves_as_a_file(sam: TestClient) -> None:
    file = uploaded(sam, ASCII_STL, "évil<script>.stl")
    created = submitted(sam, upload_id=file["id"])

    response = sam.get(f"{REQUESTS}/{created['id']}/file")

    assert response.status_code == 200
    assert response.content == ASCII_STL
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"] == (
        "attachment; filename=\"_vil_script_.stl\"; filename*=UTF-8''%C3%A9vil_script_.stl"
    )


def test_editors_and_admins_download_any_requests_file(app: FastAPI, sam: TestClient) -> None:
    created = submitted(sam, upload_id=uploaded(sam, three_mf())["id"])
    path = f"{REQUESTS}/{created['id']}/file"

    assert signed_in(app, Role.EDITOR).get(path).status_code == 200
    assert signed_in(app, Role.ADMIN).get(path).status_code == 200


def test_other_requesters_and_viewers_cannot_download(app: FastAPI, sam: TestClient) -> None:
    created = submitted(sam, upload_id=uploaded(sam, three_mf())["id"])
    path = f"{REQUESTS}/{created['id']}/file"

    assert person(app, "maya").get(path).status_code == 404
    assert person(app, "theo", requester=False).get(path).status_code == 403


def test_a_former_requester_still_downloads_their_file(client: TestClient, sam: TestClient) -> None:
    created = submitted(sam, upload_id=uploaded(sam, three_mf())["id"])
    client.patch("/api/v1/users/1", json={"requester": False}, headers=admin())

    assert sam.get(f"{REQUESTS}/{created['id']}/file").status_code == 200


def test_a_request_without_a_file_has_nothing_to_download(sam: TestClient) -> None:
    created = submitted(sam)

    assert sam.get(f"{REQUESTS}/{created['id']}/file").status_code == 404


def test_a_file_missing_from_disk_is_shown_as_missing_and_can_be_uploaded_again(
    sam: TestClient, files_dir: Path
) -> None:
    created = submitted(sam, upload_id=uploaded(sam, three_mf())["id"])
    for path in files_dir.iterdir():
        path.unlink()

    read = sam.get(f"{REQUESTS}/{created['id']}").json()
    assert read["file"]["missing"] is True
    assert sam.get(f"{REQUESTS}/{created['id']}/file").status_code == 404

    again = edit(sam, created["id"], upload_id=uploaded(sam, three_mf())["id"]).json()
    assert again["file"]["missing"] is False


def test_a_file_missing_from_disk_does_not_count_as_the_model(
    sam: TestClient, files_dir: Path
) -> None:
    created = submitted(sam, link=None, notes="", upload_id=uploaded(sam, three_mf())["id"])
    for path in files_dir.iterdir():
        path.unlink()

    response = edit(sam, created["id"], link=None, notes="", title="Dragon v2")

    assert response.status_code == 422
    assert set(response.json()["detail"]["problems"]) == {"notes"}
