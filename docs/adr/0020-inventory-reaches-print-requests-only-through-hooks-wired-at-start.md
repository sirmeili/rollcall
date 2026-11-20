# Inventory reaches Print Requests only through hooks wired in at start

Inventory never imports Print Requests (ADR-0014), but holding filament (#77) needs it to in two places: Spool detail must name the requests holding a spool, and waiting requests must take filament as soon as stock changes. So Inventory defines each hook, and `main.py`, which sees both modules, plugs Print Requests into it when the app starts:

- **Asking: who holds this spool.** Inventory's `HolderReader` (`api/spool_holders.py`) is answered by `api/request_holders.py`, kept on `app.state` and read by the spool routes (#163).
- **Telling: stock changed.** Inventory notes each change on its session (`services/stock_changes.changed`): a spool event or undo, a new grams left from the AMS or by hand, a catalog link worked out or set, or a hold released. `stock_changes.on_change` puts a SQLAlchemy `before_commit` listener on the app's session factory, which runs Print Requests' retry once, in the same session and transaction, just before a commit that follows a change (#164).

The second hook is on the session factory, not `app.state`, because stock also changes outside any request: the printer link applies AMS reports in its own thread and session, and the catalog sync updates links in a background thread, both with sessions from the app's factory. Calling the retry by hand at each trigger would run it before the change was finished (the AMS sets grams left after recording Opened) or need every route and thread to remember the call. A background job would add a thread, and a gap in which a delivered spool is promised to no one.

## Consequences

- A commit after a stock change also retries waiting requests, so a scan, an AMS report or a catalog sync can move requests to Queued in its own transaction. An error in the retry fails that commit.
- Only sessions from the app's factory react. A session made elsewhere, such as in a test or an admin command, changes stock without a retry until the next change through the app.
- A new question for Print Requests is a new hook of the first kind; a new trigger is one `stock_changes.changed` call in Inventory, and a new reaction one more `on_change` in `main.py`.
