"""Read the Open Filament Database's (OFDB's) JSON export into catalog rows.

The export (`json/all.json.gz`) lists every brand, filament, variant, size, store and
purchase link. Only Bambu Lab's are kept. Records refer to each other by their `id`, which
OFDB derives from names and can change; each also has a `uuid`, which stays, and the
catalog is keyed by that.

Every field the catalog needs is checked. Anything wrong (an incomplete download, bad JSON,
a missing or malformed field) raises ExportInvalid with a short reason, so the sync can
keep the previous catalog.
"""

import json
import zlib
from dataclasses import dataclass
from typing import Annotated, Any

from pydantic import BaseModel, Field, ValidationError

BAMBU_LAB_SLUG = "bambu_lab"
# The export is about 14 MB of JSON today; this leaves room to grow and stops a gzip bomb.
MAX_JSON_BYTES = 256 * 1024 * 1024
_CHUNK = 1024 * 1024
MAX_REASON = 200

Uuid = Annotated[str, Field(min_length=1, max_length=36)]
Name = Annotated[str, Field(min_length=1, max_length=200)]
Hex = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]


class ExportInvalid(ValueError):
    """The export can't be used. The message is a short reason, safe to show an Admin."""


class _Record(BaseModel):
    uuid: Uuid
    id: str
    moved_from: list[Uuid] | None = None


class _Brand(_Record):
    name: Name
    slug: str


class _Filament(_Record):
    name: Name
    material: Annotated[str, Field(min_length=1, max_length=64)]
    brand_id: str
    density: float | None = None
    min_print_temperature: int | None = None
    max_print_temperature: int | None = None
    min_bed_temperature: int | None = None
    max_bed_temperature: int | None = None


class _Variant(_Record):
    name: Name
    color_hex: Hex
    color_hexes: list[Hex] | None = None
    discontinued: bool
    filament_id: str


class _Size(_Record):
    variant_id: str
    filament_weight: float
    spool_refill: bool = False
    article_number: Annotated[str, Field(max_length=64)] | None = None
    discontinued: bool


class _PurchaseLink(BaseModel):
    size_id: str
    url: Annotated[str, Field(min_length=1, max_length=2000)]
    store_id: str | None = None


@dataclass(frozen=True)
class CatalogExport:
    """Bambu Lab's part of an export, as rows for the catalog tables, in OFDB's order."""

    version: str
    brand: dict[str, Any]
    filaments: list[dict[str, Any]]
    variants: list[dict[str, Any]]
    sizes: list[dict[str, Any]]


def decompress(raw: bytes) -> bytes:
    """Gunzip the download, refusing one that is cut short or unreasonably large."""
    inflater = zlib.decompressobj(wbits=31)  # gzip framing
    out = bytearray()
    try:
        data = raw
        while not inflater.eof:
            chunk = inflater.decompress(data, _CHUNK)
            data = inflater.unconsumed_tail
            if not chunk and not data:
                break  # all input used and nothing more comes out: cut short
            out += chunk
            if len(out) > MAX_JSON_BYTES:
                raise ExportInvalid("export too large")
    except zlib.error:
        raise ExportInvalid("download is not a valid gzip file") from None
    if not inflater.eof:
        raise ExportInvalid("download incomplete")
    return bytes(out)


def parse_export(raw: bytes) -> CatalogExport:
    """Bambu Lab's filament lines, catalog colors and sizes from a gzipped export."""
    try:
        data = json.loads(decompress(raw))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ExportInvalid("export is not valid JSON") from None
    if not isinstance(data, dict):
        raise ExportInvalid("export is not a JSON object")
    version = data.get("version")
    if not isinstance(version, str) or not 0 < len(version) <= 64:
        raise ExportInvalid("export has no version")
    tables = {name: _table(data, name) for name in _TABLES}

    brands = [r for r in tables["brands"] if r.get("slug") == BAMBU_LAB_SLUG]
    if len(brands) != 1:
        raise ExportInvalid("export has no Bambu Lab brand")
    brand = _check(_Brand, "brands", brands[0])
    filaments = _children(tables["filaments"], "brand_id", {brand.id}, _Filament, "filaments")
    if not filaments:
        raise ExportInvalid("export has no Bambu Lab filament lines")
    variants = _children(
        tables["variants"], "filament_id", {f.id for f in filaments}, _Variant, "variants"
    )
    sizes = _children(tables["sizes"], "variant_id", {v.id for v in variants}, _Size, "sizes")
    links = _children(
        tables["purchase_links"], "size_id", {s.id for s in sizes}, _PurchaseLink, "purchase_links"
    )
    stores = {r.get("id"): r.get("name") for r in tables["stores"]}

    for name, records in (("filaments", filaments), ("variants", variants), ("sizes", sizes)):
        if len({r.uuid for r in records}) != len(records):
            raise ExportInvalid(f"export repeats a UUID in {name}")
        # Records point at each other by id, so a repeated id would attach to the wrong one.
        if len({r.id for r in records}) != len(records):
            raise ExportInvalid(f"export repeats an id in {name}")
    by_id = {
        "filament": {f.id: f.uuid for f in filaments},
        "variant": {v.id: v.uuid for v in variants},
    }
    links_by_size: dict[str, list[dict[str, str | None]]] = {}
    for link in links:
        store = stores.get(link.store_id)
        links_by_size.setdefault(link.size_id, []).append(
            {"store": store if isinstance(store, str) else None, "url": link.url}
        )

    return CatalogExport(
        version=version,
        brand={"uuid": brand.uuid, "name": brand.name, "moved_from": brand.moved_from or []},
        filaments=[_filament_row(f, i, brand.uuid) for i, f in enumerate(filaments)],
        variants=[_variant_row(v, i, by_id["filament"]) for i, v in enumerate(variants)],
        sizes=[_size_row(s, by_id["variant"], links_by_size) for s in sizes],
    )


_TABLES = ("brands", "filaments", "variants", "sizes", "stores", "purchase_links")


def _table(data: dict[str, Any], name: str) -> list[dict[str, Any]]:
    table = data.get(name)
    if not isinstance(table, list) or not all(isinstance(r, dict) for r in table):
        raise ExportInvalid(f"export has no {name} list")
    return table


def _check[M: BaseModel](model: type[M], table: str, record: dict[str, Any]) -> M:
    try:
        return model.model_validate(record)
    except ValidationError as error:
        first = error.errors()[0]
        field = ".".join(str(part) for part in first["loc"])
        problem = "missing" if first["type"] == "missing" else "not valid"
        raise ExportInvalid(f"export has a {problem} field: {table}.{field}"[:MAX_REASON]) from None


def _children[M: BaseModel](
    table: list[dict[str, Any]], key: str, parents: set[str], model: type[M], name: str
) -> list[M]:
    """The records whose `key` names one of `parents`, checked."""
    return [_check(model, name, r) for r in table if r.get(key) in parents]


def _hex(value: str) -> str:
    return value.removeprefix("#").upper()


def _filament_row(f: _Filament, position: int, brand_uuid: str) -> dict[str, Any]:
    return {
        "uuid": f.uuid,
        "brand_uuid": brand_uuid,
        "position": position,
        "name": f.name,
        "material": f.material,
        "density": f.density,
        "min_print_temperature": f.min_print_temperature,
        "max_print_temperature": f.max_print_temperature,
        "min_bed_temperature": f.min_bed_temperature,
        "max_bed_temperature": f.max_bed_temperature,
        "moved_from": f.moved_from or [],
    }


def _variant_row(v: _Variant, position: int, filaments: dict[str, str]) -> dict[str, Any]:
    main = _hex(v.color_hex)
    hexes = [_hex(h) for h in v.color_hexes or []]
    # OFDB lists a multi-color variant's first color both as color_hex and in color_hexes.
    if hexes and hexes[0] == main:
        hexes = hexes[1:]
    return {
        "uuid": v.uuid,
        "filament_uuid": filaments[v.filament_id],
        "position": position,
        "name": v.name,
        "color_hex": main,
        "extra_hexes": hexes,
        "discontinued": v.discontinued,
        "moved_from": v.moved_from or [],
    }


def _size_row(
    s: _Size, variants: dict[str, str], links: dict[str, list[dict[str, str | None]]]
) -> dict[str, Any]:
    return {
        "uuid": s.uuid,
        "variant_uuid": variants[s.variant_id],
        "filament_weight": s.filament_weight,
        "refill": s.spool_refill,
        "article_number": s.article_number,
        "discontinued": s.discontinued,
        "purchase_links": links.get(s.id, []),
        "moved_from": s.moved_from or [],
    }
