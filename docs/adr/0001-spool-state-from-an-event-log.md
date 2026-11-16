# Spool state comes from an append-only event log

A spool's state (sealed, open, empty, or unknown) is derived by replaying its events in order of `occurred_at`, then `recorded_at`; events are never edited or deleted, and an undo is a new `revert` event. Only state changes are events (received, opened, empty, undo): location and notes are edited on the spool directly. We chose this over storing the state on the spool so that queued and out-of-order scans, undo, and a full audit trail all fall out of one rule, at the cost of replaying events to read a state.
