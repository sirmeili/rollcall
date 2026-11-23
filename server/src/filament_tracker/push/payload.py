"""What a phone notification carries: its kind, title, text, the path of the page it opens and,
for some, the server path of a photo to show, as JSON. It stays well under the 4 KB a Web Push
may carry once encrypted: a long text, then a long title, is cut short to fit."""

import json

# The plain payload's limit; encryption adds 103 bytes (RFC 8291), well under 4096.
MAX_PAYLOAD_BYTES = 3072
ELLIPSIS = "…"


def _encoded(fields: dict[str, str]) -> bytes:
    return json.dumps(fields, ensure_ascii=False, separators=(",", ":")).encode()


def _cut(value: str, over: int) -> str:
    """`value` shortened by at least `over` bytes of UTF-8, ending in an ellipsis."""
    raw = value.encode()
    keep = max(0, len(raw) - over - len(ELLIPSIS.encode()))
    return raw[:keep].decode(errors="ignore") + ELLIPSIS


def phone_payload(kind: str, title: str, text: str, path: str, photo: str | None = None) -> bytes:
    """The payload, with the text and then the title cut short if it would be too long. A
    `photo` is named only when there is one."""
    fields = {"kind": kind, "title": title, "text": text, "path": path}
    if photo is not None:
        fields["photo"] = photo
    encoded = _encoded(fields)
    for name in ("text", "title"):
        while len(encoded) > MAX_PAYLOAD_BYTES and fields[name] not in ("", ELLIPSIS):
            fields[name] = _cut(fields[name], len(encoded) - MAX_PAYLOAD_BYTES)
            encoded = _encoded(fields)
    return encoded
