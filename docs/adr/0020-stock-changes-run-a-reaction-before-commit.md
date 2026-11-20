# Stock changes run a reaction before the commit

Waiting print requests must take filament as soon as Inventory's stock changes, but Inventory never imports Print Requests (ADR-0014), and the changes happen in different places: API routes, the printer link's thread with its own session, and the catalog sync's background thread. Inventory notes each change on its session (`stock_changes.changed`), and the app wires a reaction to its session factory (`stock_changes.on_change`): a SQLAlchemy `before_commit` listener that, after a change, runs Print Requests' retry once, in the same session and transaction as the change, in whatever thread made it. We chose this over a listener registry called by hand at each trigger, which would run mid-change (before the AMS's grams or the spool's state were final) or need every route and thread to remember a call, and over a background job, which would add a thread and a gap where a delivered spool is still promised to no one.

## Consequences

- Any commit after a stock change also retries waiting requests, so a scan, an AMS report or a catalog sync can move requests to Queued in the same transaction. An error in the retry fails that commit.
- Only sessions made by the app's factory react. A session made elsewhere, such as in a test or an admin command, changes stock without retrying until the next change through the app.
- A new trigger is one `stock_changes.changed` call in Inventory; a new reaction is one more `on_change` in the app wiring.
