"""Print Requests' one refusal: something a caller asked for that is not done, and why.

A refusal is raised before anything is committed, so nothing is saved. Its kind says what
went wrong; the app's exception handler turns each kind into its status code.
"""

from enum import Enum


class Kind(Enum):
    NOT_FOUND = "not found"  # No such request, or one the caller may not see; or part of it.
    FORBIDDEN = "forbidden"  # The caller sees the request but may not do this to it.
    STALE = "stale"  # The request has moved on from the status the caller saw it in.
    INVALID = "invalid"  # What was sent has problems, by field.


class Refused(Exception):
    """A refusal of `kind`, with a message, or for INVALID each field's problem."""

    def __init__(self, kind: Kind, message: str = "", problems: dict[str, str] | None = None):
        self.kind = kind
        self.problems = problems or {}
        self.message = message or "; ".join(self.problems.values())
        super().__init__(self.message)

    @classmethod
    def not_found(cls, message: str) -> "Refused":
        return cls(Kind.NOT_FOUND, message)

    @classmethod
    def forbidden(cls, message: str) -> "Refused":
        return cls(Kind.FORBIDDEN, message)

    @classmethod
    def stale(cls, message: str) -> "Refused":
        return cls(Kind.STALE, message)

    @classmethod
    def invalid(cls, problems: dict[str, str]) -> "Refused":
        return cls(Kind.INVALID, problems=problems)
