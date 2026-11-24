"""The Phone notifications settings group, read as the Firebase project phones of the google
app flavor get phone notifications through (FCM). Firebase counts as set up only with all
five settings: the four client settings phones start Firebase with, and the service-account
key the server sends with."""

from dataclasses import dataclass, field

from filament_tracker.app_settings.store import SettingsStore
from filament_tracker.push.fcm_account import ServiceAccountKey, parse_service_account


@dataclass(frozen=True)
class FirebaseClient:
    """What a phone starts Firebase with. None of it is secret: Firebase builds it into apps."""

    project_id: str
    app_id: str
    api_key: str
    sender_id: str


@dataclass(frozen=True)
class Firebase:
    client: FirebaseClient
    # Never shown in a repr, so never in a log or a traceback.
    account: ServiceAccountKey = field(repr=False)


def firebase(store: SettingsStore) -> Firebase | None:
    """Firebase as set up now, or None when any of the five settings is missing."""
    values = [
        store.text(key) for key in ("firebase_project_id", "firebase_app_id", "firebase_api_key")
    ]
    sender = store.text("firebase_sender_id")
    secret = store.secret("firebase_service_account")
    project_id, app_id, api_key = values
    if not (project_id and app_id and api_key and sender and secret):
        return None
    try:
        account = parse_service_account(secret.get_secret_value())
    except ValueError:
        # Only from .env, which is checked when saved in the app.
        return None
    return Firebase(FirebaseClient(project_id, app_id, api_key, sender), account)
