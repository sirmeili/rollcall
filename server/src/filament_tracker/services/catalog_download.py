"""Download one catalog source's file, asking with If-None-Match and If-Modified-Since
whether it changed since the copy in use.

Every failure raises DownloadFailed with a short reason that names the server (such as
"could not reach OFDB"), never its answer.
"""

from dataclasses import dataclass

import httpx

TIMEOUT = httpx.Timeout(30.0, read=60.0)
USER_AGENT = "RollCall catalog sync"


class DownloadFailed(Exception):
    """The download failed; the message is the short reason recorded."""


@dataclass(frozen=True)
class Download:
    body: bytes
    etag: str | None
    last_modified: str | None
    not_modified: bool = False


@dataclass(frozen=True)
class Copy:
    """What the server sent with the copy in use, if there is one."""

    etag: str | None
    last_modified: str | None


def download(
    url: str,
    *,
    server: str,
    copy: Copy | None,
    max_bytes: int,
    transport: httpx.BaseTransport | None,
) -> Download:
    """The file at `url`, or Not modified (304) when `copy` is still current. `server` names
    it in failure reasons."""
    headers = {"User-Agent": USER_AGENT}
    if copy is not None and copy.etag:
        headers["If-None-Match"] = copy.etag
    if copy is not None and copy.last_modified:
        headers["If-Modified-Since"] = copy.last_modified
    try:
        with (
            httpx.Client(transport=transport, timeout=TIMEOUT, follow_redirects=True) as client,
            client.stream("GET", url, headers=headers) as response,
        ):
            etag = response.headers.get("ETag")
            last_modified = response.headers.get("Last-Modified")
            if response.status_code == 304 and copy is not None:
                return Download(b"", etag, last_modified, not_modified=True)
            if response.status_code != 200:
                raise DownloadFailed(f"{server} answered {response.status_code}")
            body = bytearray()
            for chunk in response.iter_bytes():
                body += chunk
                if len(body) > max_bytes:
                    raise DownloadFailed("download too large")
    except httpx.TimeoutException:
        raise DownloadFailed(f"{server} did not answer in time") from None
    except (httpx.RemoteProtocolError, httpx.ReadError):
        raise DownloadFailed("download incomplete") from None
    except httpx.HTTPError:
        raise DownloadFailed(f"could not reach {server}") from None
    return Download(bytes(body), etag, last_modified)
