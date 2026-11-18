"""The rules a print request's fields follow, checked together so every mistake is reported
at once: when submitting and on every edit.

- a title, after trimming, of up to 120 characters
- a quantity from 1 to 100
- a needed-by date, if any, not in the past in the server's time zone (checked when it is
  set or changed, so an older request can still be edited after its date)
- a link, if any, is an absolute http or https URL; it is only ever stored and shown
- the model rule: a file, a link or both; with neither, the notes must not be empty
"""

from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlsplit
from uuid import UUID

from filament_tracker.domain.enums import Priority
from filament_tracker.print_requests.choices import ChoiceInput

QUANTITY_MIN = 1
QUANTITY_MAX = 100

TITLE = "title"
NOTES = "notes"
QUANTITY = "quantity"
NEEDED_BY = "needed_by"
PRIORITY = "priority"
LINK = "link"
FILE = "file"
CHOICES = "choices"


class Problems(ValueError):
    """The request can't be saved; each field's problem."""

    def __init__(self, problems: dict[str, str]) -> None:
        super().__init__("; ".join(problems.values()))
        self.problems = problems


@dataclass
class RequestFields:
    """What a Requester sends for a new request, or for an edit (all of it again)."""

    title: str
    notes: str = ""
    quantity: int = 1
    needed_by: date | None = None
    priority: Priority = Priority.NORMAL
    link: str | None = None
    choices: list[ChoiceInput] = field(default_factory=list)
    # A checked upload to save as the model file (replacing any file it has).
    upload_id: UUID | None = None
    # On an edit: take the model file off the request.
    remove_file: bool = False

    def cleaned(self) -> "RequestFields":
        link = (self.link or "").strip() or None
        return RequestFields(
            title=self.title.strip(),
            notes=self.notes.strip(),
            quantity=self.quantity,
            needed_by=self.needed_by,
            priority=self.priority,
            link=link,
            choices=[
                ChoiceInput(c.product_id, c.catalog_color, c.note.strip()) for c in self.choices
            ],
            upload_id=self.upload_id,
            remove_file=self.remove_file,
        )


def is_web_link(link: str) -> bool:
    parts = urlsplit(link)
    return parts.scheme.lower() in ("http", "https") and bool(parts.hostname)


def check(
    fields: RequestFields, *, today: date, check_date: bool, has_file: bool
) -> dict[str, str]:
    """Each field's problem; empty when the request may be saved."""
    problems = {}
    if not fields.title:
        problems[TITLE] = "Enter a title."
    if not QUANTITY_MIN <= fields.quantity <= QUANTITY_MAX:
        problems[QUANTITY] = f"Enter a quantity from {QUANTITY_MIN} to {QUANTITY_MAX}."
    if check_date and fields.needed_by is not None and fields.needed_by < today:
        problems[NEEDED_BY] = (
            "Needed by can't be in the past. Pick today or later, or leave it empty."
        )
    if fields.link is not None and not is_web_link(fields.link):
        problems[LINK] = "Enter a link that starts with http:// or https://."
    if not has_file and fields.link is None and not fields.notes:
        problems[NOTES] = "Add a file or a link, or say in the notes where the model is."
    return problems
