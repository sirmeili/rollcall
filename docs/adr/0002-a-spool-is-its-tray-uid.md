# A spool is identified by its tray UID

Both tags on a roll share one tray UID, and that is the spool's identity; the tag UIDs are not. A refill or a second roll of the same product has its own tray UID, so it is a new spool. A spool added by hand before its tag can be read has no tray UID: it is a placeholder, and the first scan of that product's tag links to the oldest placeholder and is flagged for review.
