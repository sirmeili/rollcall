# Grams left is a figure on the spool, not part of the event log

A spool's grams left is stored on the spool and edited in place, like its location and notes, rather than derived from events (ADR-0001 keeps events for state changes only). The AMS sets it from the net weight times its remaining %, and the latest report wins over a figure an Admin typed. An Admin sets it by hand for spools the AMS doesn't see, such as TPU. We chose this for #77, so holds have grams to work against before anything measures usage, over recording usage events now: those would double-count against the AMS's remaining % on an Open spool.

## Consequences

- A change to grams left can't be undone and leaves no history.
- Holds are released on Done without recording what was used, so available grams read high until the AMS next reports, or until an Admin updates a spool that isn't in the AMS.
- Print jobs (3.2) will have to choose between recording usage as events and keeping this figure, and migrate one to the other.
