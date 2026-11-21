# RollCall

RollCall tracks Bambu Lab filament spools from delivery to empty, by reading their RFID tags, and (planned) handles print requests against that stock.

## Language

**RollCall**:
The app's name.
_Avoid_: Filament Tracker, Spoolhouse (the code keeps `filament_tracker`, `ft-` and `ftd_` until the code rename)

**Inventory**:
The count of each product's spools in each state. Also the module that Print Requests depends on.

**Delivery**:
Unpacking new spools with a phone: each is scanned as Received and listed together until the app closes.

### Tags

**Tag**:
One of the two RFID tags on a Bambu spool.

**Tag UID**:
A tag's own 4-byte ID, different on each tag. It never identifies a spool.
_Avoid_: UID on its own

**Tray UID**:
The ID that both tags of a spool share, and the spool's identity. The AMS reports it as `tray_uuid`.
_Avoid_: Tray UUID, tray ID

**Unidentified tag**:
A tag that was read but could not be decoded or matched to a spool. It is kept for Review.

**Key-derivation constant**:
The published value that tag keys are derived from, set as `BAMBU_KDF_SALT`.
_Avoid_: Salt, tag key constant

### Scanning

**Scanner**:
Anything that reads a spool's tags and sends scans to the server: a handheld scanner or a phone.
_Avoid_: Device, reader, unit

**Handheld scanner**:
The dedicated scanner hardware: a CYD board with a PN532 in a printed case.
_Avoid_: Scanner device, CYD (except when talking about the board itself)

**Phone**:
The Android app acting as a scanner. It also holds the full web app.
_Avoid_: Phone scanner device, mobile device

**Reader**:
The NFC chip that reads tags, the PN532 in a handheld scanner. Not the whole scanner.

**Scan**:
One read of a spool's tags sent by a scanner, carrying either a lookup or an action.
_Avoid_: Scan event

**Lookup**:
A scan that only identifies the spool and records nothing.

**Pairing**:
Giving a scanner its device token for one server.

**User's phone**:
A phone set up by signing in. Its scans are recorded as that user's, and it can do only what their role allows.

**Shared phone**:
A phone paired with a code or QR code, belonging to no user.

**Unlink**:
A phone forgets its server.

### People and access

**Role**:
What a user may do: Viewer, Editor or Admin.

**Requester**:
A user who may also submit print requests. It is added to a role, never held alone.
_Avoid_: Requester role

**Device token**:
The token a scanner sends its scans with.

**Machine token**:
A token with a role, for Home Assistant and scripts, made on the Settings page.
_Avoid_: Admin token, API key

**Revoke**:
Stop accepting a device token or machine token. The record is kept.

### Stock

**Spool**:
One physical roll of filament.
_Avoid_: Roll, reel

**Product**:
One kind of filament you can buy, such as Black PLA Basic. Every spool of a product shares its product key.
_Avoid_: Filament, filament product, SKU

**Product key**:
What makes two spools the same product: the material ID, variant ID and color read from their tags.

**Provisional product**:
A product not yet identified from a tag, added by hand or first seen by the AMS. The first scan of its tag, if any, fills it in.

**Placeholder**:
A spool with no tray UID, added by hand. The first scan of its product, if any, links it.

**Location**:
Where a spool is kept, written by hand, such as Shelf B or Dry box 2. Moving spools sets their location. While a spool is loaded in an AMS, its slot is shown as its location; the written one is kept and shows again when the spool leaves the AMS.
_Avoid_: Storage, place

**Low stock**:
A product whose count of Sealed spools is at or below its threshold. A threshold of 0 turns it off.
_Avoid_: Low filament (Home Assistant's name for it)

**Net weight**:
The grams of filament a spool holds when full, such as 1000 g. It comes from the tag, or is set by hand for a placeholder.
_Avoid_: Spool weight (that suggests the empty spool), total

**Grams left**:
How much filament a spool has, in grams. The AMS's remaining % sets it, and an Admin can set it by hand for a spool the AMS doesn't see. It is unknown for an Open spool with neither.
_Avoid_: Remaining grams, weight (that word is for the spool's full amount)

**Hold**:
Grams of a spool set aside for something, such as an approved print request, so they aren't promised twice. A filament choice can be held across several spools of its product. A hold is released, and kept with when and why, when the request is Done, Failed or Cancelled, or when its spool becomes Empty or Unknown.
_Avoid_: Reservation, allocation

**Available grams**:
A spool's grams minus its holds, or the sum of that over a product's spools. An estimate, so shown as "about".
_Avoid_: Free grams, stock (that word is for spool counts)

**Nearly out**:
An Open spool whose remaining % is at or below its product's cutoff. It applies only to spools in an AMS.

### Catalog

**Catalog**:
The local copy of the Open Filament Database's Bambu Lab colors.
_Avoid_: OFDB (except when talking about the source itself)

**Filament line**:
One material line in the catalog, such as PLA Basic.
_Avoid_: Filament on its own

**Catalog color**:
One color of a filament line, whether owned or not.
_Avoid_: Variant (that word is for the tag's variant ID)

**Catalog link**:
A product's tie to its catalog color. It is automatic when made from the product's tag IDs, or manual when set by a person, and a manual one is never replaced automatically. It stays in place whatever the product's stock.
_Avoid_: Owned, match (that word is for similar in-stock colors)

**Owned**:
A catalog color with at least one Sealed or Open spool of its linked product. A linked product with no spools in stock does not make its color owned.

**Bambu code**:
The 5-digit number Bambu Lab sells a catalog color under, such as 10204 for PLA Basic Hot Pink.
_Avoid_: Color code, article number, SKU

**BambuStudio color code**:
The short code BambuStudio's color code list gives each color of a filament ID, such as K0. With the filament ID it makes a tag's variant ID (GFA00 and K0 make A00-K0), which is how a tag finds its Bambu code. It is never shown in the app.
_Avoid_: Color code on its own (that is easily confused with the Bambu code)

**Similar in-stock color**:
An in-stock product whose color is within the similarity cutoff of a catalog color, in any material.
_Avoid_: Closest color

### Printer

**AMS**:
The printer's filament unit, which holds spools and reports what is loaded. An AMS HT is the single-slot kind.

**Slot**:
One spool position in an AMS.
_Avoid_: Tray (except in Bambu's field names and "tray UID")

**Remaining %**:
The AMS's estimate of how much filament is left on a loaded spool. It is known only for a spool in an AMS.

### Spool history

**Spool state**:
Where a spool is in its life: Sealed, Open, Empty or Unknown.
_Avoid_: Closed (for Sealed)

**Unknown**:
The state of a spool that has no events in effect (none recorded, or all undone), so no state can be derived.
_Avoid_: Unidentified (that word is for tags)

**Action**:
A change to a spool's state: Received, Opened or Empty. It comes from a scan, the web app or the AMS.
_Avoid_: New (except as the scanner's button label for Received), used up, emptied

**Event**:
One recorded action, or an undo, in a spool's event log. A spool's state is derived from its events.
_Avoid_: using "event" alone for a Home Assistant event

**Source**:
Where an event came from: a scanner, the web app (a person, by hand, with the user recorded) or the AMS. It belongs to the event, not the spool.
_Avoid_: Printer, ui, manual

**Undo**:
Cancel the effect of an earlier event by recording a new event that points at it.
_Avoid_: Revert

### Review

**Review**:
The queue of things a person has to settle: flagged events, unidentified tags and likely-empty suggestions. Used for this queue only.

**Flagged event**:
An event that was recorded but needs a person to check it, such as Received on a spool that is already open.

**Accept**:
Confirm that a flagged event is right.
_Avoid_: Reviewed

**Dismiss**:
Set aside an unidentified tag or a likely-empty suggestion.

**Bring back**:
Return an accepted or dismissed item to Review.

**Likely empty**:
The AMS's suggestion that a spool is empty. It never changes the spool's state on its own.

### Print requests

**Print request**:
A Requester's ask to have something printed: a model and the filament to print it in.
_Avoid_: Job (that is the printer's), order

**Filament choice**:
One filament a print request asks for: an in-stock product or a catalog color, with an optional note such as "accents". A request has one or more.

**Priority**:
How soon a print request is wanted: Urgent, Normal or No rush.

**Request history**:
The record of what happened to a print request: submitted, edited, priority or status changed, photo added or removed, by whom and when. It is never edited.
_Avoid_: Event (that word is for a spool's event log)

**Requests**:
The page listing print requests: a Requester's own, or every request for Editors and Admins.
_Avoid_: Review (that word is for the Review queue only)

**Approve**:
Agree to print a print request. It moves the request to Approved.
_Avoid_: Accept (that word is for flagged events)

**Request status**:
Where a print request is. While it goes ahead: Submitted, Approved, Waiting on Filament, Queued, Printing, Done, Picked Up. When it stops: Rejected, Cancelled, Failed.
_Avoid_: Accepted (for Approved), state (that word is for a spool), stage

**Reject**:
Decline a Submitted print request, with a reason.

**Reprint**:
Send a Failed print request on for another attempt, holding its filament again: to Queued, or to Waiting on Filament when a choice is short. It stays the same request.
_Avoid_: Retry, resubmit

**Photo**:
A picture of a finished print, added by an Admin when moving a print request to Done or later while it is Done or Picked Up. A request has up to 4.
_Avoid_: Image, attachment

**Attempt**:
One try at printing a print request. A reprint starts the next one.

### Home Assistant

**Home Assistant event**:
A message RollCall fires to Home Assistant for automations, such as a spool emptied or low stock. Always named in full.
