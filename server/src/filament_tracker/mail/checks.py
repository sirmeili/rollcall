"""The email that Send test email sends, to check the settings work."""

from html import escape

from filament_tracker.mail.message import Email

SUBJECT = "RollCall test email"
SENTENCE = "This is a test email from RollCall. Email is set up and working."


def test_email(to: str) -> Email:
    return Email(
        to=to,
        subject=SUBJECT,
        text=f"{SENTENCE}\n",
        html=f"<!doctype html><html><body><p>{escape(SENTENCE)}</p></body></html>",
    )
