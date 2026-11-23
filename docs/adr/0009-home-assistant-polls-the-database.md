# Home Assistant is fed by reading the database every 5 seconds

Entities come from a 5-second snapshot of the database, published only when changed, and events from reading new rows on the same cycle, instead of hooks on each write path. This covers every way stock changes (scanners, the web app, the AMS, undo) without touching each one. Only events recorded after the server starts are fired, so a restart never replays history into automations.

The poll always runs, whether or not Home Assistant is set up: it also notices low stock and nearly-out spools for notifications (#217).
