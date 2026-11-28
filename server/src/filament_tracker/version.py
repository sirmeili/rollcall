"""Which release this server is (ADR-0025): the version and commit the image was built with,
as the build arguments `ROLLCALL_VERSION` and `ROLLCALL_COMMIT` (docs/configuration.md)."""

import os
from collections.abc import Mapping

SHORT_COMMIT = 7


def server_version(environ: Mapping[str, str] = os.environ) -> str:
    """The release version, such as `1.4.0` or `1.4.0-rc.1`; `dev (<short commit>)` for a
    build with only a commit; `dev` for one with neither."""
    version = environ.get("ROLLCALL_VERSION", "").strip()
    if version:
        return version
    commit = environ.get("ROLLCALL_COMMIT", "").strip()
    return f"dev ({commit[:SHORT_COMMIT]})" if commit else "dev"
