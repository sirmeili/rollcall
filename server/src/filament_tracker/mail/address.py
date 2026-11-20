"""Email addresses: checked for shape only, never verified."""

import re

MAX_ADDRESS = 254
# One @, something before it, and a domain with a dot between non-empty parts. No spaces.
ADDRESS_PATTERN = re.compile(r"[^@\s]+@[^@\s.]+(\.[^@\s.]+)+")
ADDRESS_PROBLEM = "use an email address like name@example.com, at most 254 characters"


def clean_address(value: str | None) -> str | None:
    """A trimmed address, or None for an empty one. Raises ValueError for a bad one."""
    value = (value or "").strip()
    if not value:
        return None
    if len(value) > MAX_ADDRESS or not ADDRESS_PATTERN.fullmatch(value):
        raise ValueError(ADDRESS_PROBLEM)
    return value
