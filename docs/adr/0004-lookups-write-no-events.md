# Lookups write no events; repeated actions do

A lookup only identifies the spool and writes nothing, so the event log holds actions only. A repeated action (`already_in_state`) is still stored even though it changes nothing: it keeps the audit trail complete, and it takes effect if an earlier event is undone.
