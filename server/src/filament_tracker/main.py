from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from functools import partial

import httpx
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from filament_tracker.api import (
    activity,
    auth,
    catalog,
    devices,
    edits,
    email_settings,
    events,
    health,
    printers,
    push,
    request_files,
    request_holders,
    request_holds,
    request_needs,
    request_photos,
    requests,
    review,
    scans,
    setup,
    shopping_list,
    shopping_suggestions,
    stock,
    tokens,
    users,
)
from filament_tracker.api import settings as app_settings
from filament_tracker.api.errors import validation_error
from filament_tracker.api.limits import BodySizeLimitMiddleware
from filament_tracker.api.security import SecurityHeadersMiddleware
from filament_tracker.api.session_renewal import SessionRenewalMiddleware
from filament_tracker.app_settings.crypto import SecretBox, load_key
from filament_tracker.app_settings.offline import database_file
from filament_tracker.app_settings.store import SettingsStore
from filament_tracker.config import Settings
from filament_tracker.db.engine import create_db_engine, create_session_factory
from filament_tracker.db.migrate import upgrade
from filament_tracker.ha.link import HomeAssistantLink
from filament_tracker.mail.sender import MailSender
from filament_tracker.mail.settings import smtp_server
from filament_tracker.mail.smtp import SmtpSender
from filament_tracker.mail.transport import MailTransport
from filament_tracker.push.keys import vapid_keys
from filament_tracker.push.sender import PushSender
from filament_tracker.push.transport import HttpPushTransport, PushTransport
from filament_tracker.notifications.backup import backup_failed_sender
from filament_tracker.notifications.low_stock import LowStockEmails
from filament_tracker.notifications.nearly_out import NearlyOutEmails
from filament_tracker.poll import Poll
from filament_tracker.print_requests import retrying
from filament_tracker.print_requests.files import MAX_MODEL_BYTES, ModelFiles, files_dir
from filament_tracker.print_requests.photos import MAX_PHOTO_BYTES
from filament_tracker.printer.manager import PrinterManager
from filament_tracker.services.backup import BackupScheduler
from filament_tracker.services.catalog_schedule import CatalogScheduler
from filament_tracker.services.catalog_sync import CatalogSyncer
from filament_tracker.services.cooldown import TEST_EMAIL_GAP, TEST_PUSH_GAP, Cooldown, Cooldowns
from filament_tracker.services.printers import seed_printers
from filament_tracker.services.setup import SetupGate
from filament_tracker.services.stock_changes import on_change
from filament_tracker.services.throttle import LoginThrottle
from filament_tracker.webapp import default_web_dir, mount_web_app

API_PREFIX = "/api/v1"


def _backups(
    settings: Settings, store: SettingsStore, on_failure: Callable[[str], None] | None = None
) -> BackupScheduler | None:
    """Start the nightly backups, if BACKUP_DIR is set and the database is a file."""
    source = database_file(settings.database_url)
    if settings.backup_dir is None or source is None:
        return None
    scheduler = BackupScheduler(source, settings.backup_dir, store.time_zone, on_failure=on_failure)
    scheduler.start()
    return scheduler


def create_app(
    settings: Settings | None = None,
    *,
    catalog_transport: httpx.BaseTransport | None = None,
    mail_transport: MailTransport | None = None,
    push_transport: PushTransport | None = None,
) -> FastAPI:
    """The server. `catalog_transport` replaces the network for catalog syncs,
    `mail_transport` the SMTP sender for emails and `push_transport` the push services for
    phone notifications, in tests."""
    settings = settings or Settings()
    mail_transport = mail_transport or SmtpSender()
    push_transport = push_transport or HttpPushTransport()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        upgrade(settings.database_url)
        engine = create_db_engine(settings.database_url)
        app.state.session_factory = create_session_factory(engine)
        # Waiting print requests take filament as soon as stock changes (ADR-0020).
        on_change(app.state.session_factory, retrying.retry)
        box = SecretBox(load_key(settings.settings_key, settings.database_url))
        app.state.secret_box = box
        with app.state.session_factory() as session:
            seed_printers(session, box, settings.printers)
        printer_links = PrinterManager(app.state.session_factory, box)
        app.state.printers = printer_links
        printer_links.start()
        store = SettingsStore(settings, app.state.session_factory, box)
        app.state.settings_store = store
        home_assistant = HomeAssistantLink(store, app.state.session_factory)
        app.state.home_assistant = home_assistant
        home_assistant.start()
        app.state.setup_gate.start(app.state.session_factory)
        mail = MailSender(mail_transport, lambda: smtp_server(store))
        app.state.mail = mail
        mail.start()
        app.state.vapid_keys = vapid_keys(app.state.session_factory, box)
        phones = PushSender(push_transport, app.state.session_factory, app.state.vapid_keys)
        app.state.push = phones
        phones.start()
        # Where emails link to: PUBLIC_URL, read when each is built.
        public_url = partial(store.text, "public_url")
        # Always running, Home Assistant or not (ADR-0009).
        poll = Poll(
            app.state.session_factory,
            [
                LowStockEmails(mail, public_url),
                NearlyOutEmails(mail, public_url),
                home_assistant.changed,
            ],
        )
        app.state.poll = poll
        poll.start()
        catalog = CatalogSyncer(app.state.session_factory, transport=catalog_transport)
        app.state.catalog = catalog
        catalog_scheduler = CatalogScheduler(
            catalog, schedule=store.catalog_sync, time_zone=store.time_zone
        )
        catalog_scheduler.start()
        backup_failed = backup_failed_sender(app.state.session_factory, mail, public_url)
        backups = _backups(settings, store, backup_failed)
        app.state.backups = backups
        try:
            yield
        finally:
            if backups is not None:
                backups.stop()
            catalog_scheduler.stop()
            poll.stop()
            phones.stop()
            mail.stop()
            home_assistant.stop()
            printer_links.stop()
            engine.dispose()

    app = FastAPI(title="RollCall", lifespan=lifespan)
    app.state.settings = settings
    app.state.login_throttle = LoginThrottle()
    # Wrong setup codes are throttled like sign-ins, but apart from them.
    app.state.setup_throttle = LoginThrottle()
    app.state.setup_gate = SetupGate()
    app.state.test_email_cooldown = Cooldown(TEST_EMAIL_GAP)
    app.state.test_push_cooldowns = Cooldowns(TEST_PUSH_GAP)
    app.state.model_files = ModelFiles(files_dir(settings.database_url))
    # Spool detail names the requests holding a spool through this (ADR-0020).
    app.state.holder_reader = request_holders.holding_requests
    app.state.request_needs_reader = request_needs.request_needs
    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_middleware(
        BodySizeLimitMiddleware,
        larger={
            ("POST", API_PREFIX + request_files.UPLOAD_PATH): MAX_MODEL_BYTES,
            ("POST", API_PREFIX + request_photos.PHOTO_UPLOAD_PATH): MAX_PHOTO_BYTES,
        },
    )
    app.add_middleware(SessionRenewalMiddleware)
    # Added last, so it runs first: headers go on every response, including a 413.
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)
    for module in (
        health,
        auth,
        scans,
        stock,
        edits,
        activity,
        review,
        devices,
        printers,
        events,
        users,
        tokens,
        setup,
        app_settings,
        email_settings,
        push,
        catalog,
        shopping_list,
        shopping_suggestions,
        request_files,
        request_holds,
        request_photos,
        requests,
    ):
        app.include_router(module.router, prefix=API_PREFIX)
    mount_web_app(app, settings.web_dir or default_web_dir())
    return app
