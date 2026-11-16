# Uncertain events are recorded and flagged, never refused

An event that doesn't fit the spool's state (received on an open or empty spool, a spool first seen by the AMS, an empty spool reopened from a scanner) is still recorded, and flagged for review instead of being refused. Scanners queue offline and events arrive late, so refusing would lose real history; a person settles it on the Review page with Accept, Undo or a fix by hand. A reopen from the web app is a deliberate correction and is not flagged.
