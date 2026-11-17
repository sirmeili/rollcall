"""The catalog read: filament lines with their catalog colors, for Viewers and above."""

from api_helpers import CSRF, admin, browser, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ofdb_fake import FakeSource, export, gz, ok, refresh, status, variant

from filament_tracker.domain.enums import Role

CATALOG = "/api/v1/catalog"


def read(client: TestClient) -> dict:
    response = client.get(CATALOG, headers=admin())
    assert response.status_code == 200, response.text
    return response.json()


def test_before_the_first_sync_the_catalog_is_empty(client: TestClient) -> None:
    body = read(client)

    assert body["synced"] is False
    assert body["lines"] == []
    assert body["dataset_version"] is None
    assert body["last_success_at"] is None


def test_lists_filament_lines_with_their_catalog_colors_in_catalog_order(
    client: TestClient,
) -> None:
    synced = refresh(client)

    body = read(client)

    assert body["synced"] is True
    assert body["dataset_version"] == "2026.11.14"
    assert body["last_success_at"] == synced["ofdb"]["last_success_at"]
    assert [(line["name"], line["material"]) for line in body["lines"]] == [
        ("PLA Basic", "PLA"),
        ("PETG HF", "PETG"),
    ]
    pla, petg = body["lines"]
    assert pla["uuid"] == "fil-pla-basic"
    assert [c["name"] for c in pla["colors"]] == ["Black", "Jade White", "Arctic Whisper"]
    black, jade, gradient = pla["colors"]
    assert black["uuid"] == "var-black"
    assert black["hexes"] == ["000000"]
    assert black["discontinued"] is False
    assert black["multi_color"] is False
    assert jade["hexes"] == ["FFFFFF"]
    assert gradient["hexes"] == ["9CDBD9", "FFFFFF"]
    assert gradient["multi_color"] is True
    (cream,) = petg["colors"]
    assert cream["discontinued"] is True


def test_says_which_multi_color_catalog_colors_are_gradients(
    client: TestClient, ofdb: FakeSource
) -> None:
    data = export()
    for v in data["variants"]:
        if v["uuid"] == "var-gradient":
            v["traits"] = {"gradual_color_change": True}
        if v["uuid"] == "var-black":
            v["traits"] = {"glow": False}
    data["variants"].append(
        variant(
            "var-dual",
            "Aurora Purple",
            "#7F3696",
            "id-fil-pla-basic",
            color_hexes=["#7F3696", "#006EC9"],
            traits={"coextruded": True},
        )
    )
    ofdb.serve(ok(gz(data)))
    refresh(client)

    (pla, _) = read(client)["lines"]

    gradient = {c["name"]: c["gradient"] for c in pla["colors"]}
    assert gradient == {
        "Black": False,
        "Jade White": False,
        "Arctic Whisper": True,
        "Aurora Purple": False,
    }


def test_a_failed_sync_still_reads_the_last_good_copy(client: TestClient, ofdb: FakeSource) -> None:
    refresh(client)
    ofdb.serve(status(500))
    refresh(client)

    body = read(client)

    assert body["synced"] is True
    assert len(body["lines"]) == 2


def test_every_role_can_read_it(app: FastAPI, client: TestClient) -> None:
    refresh(client)
    for role in Role:
        user = signed_in(app, role, username=f"{role.value}-reader")
        assert user.get(CATALOG).status_code == 200


def test_signing_in_is_needed(app: FastAPI, client: TestClient) -> None:
    assert browser(app).get(CATALOG, headers=CSRF).status_code == 401
