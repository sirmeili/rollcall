"""The Email settings group, read as the SMTP server to send with."""

from filament_tracker.app_settings.store import SettingsStore
from filament_tracker.mail.transport import Security, SmtpServer

DEFAULT_PORT = 587
DEFAULT_SECURITY: Security = "starttls"


def smtp_server(store: SettingsStore) -> SmtpServer | None:
    """The SMTP server from the saved settings, or None when email is off (no host)."""
    host = store.text("smtp_host")
    if host is None:
        return None
    security = store.text("smtp_security") or DEFAULT_SECURITY
    return SmtpServer(
        host=host,
        port=int(store.text("smtp_port") or DEFAULT_PORT),
        security=security,  # type: ignore[arg-type] - checked by the registry
        user=store.text("smtp_user"),
        password=store.secret("smtp_password"),
        from_address=store.text("smtp_from"),
    )
