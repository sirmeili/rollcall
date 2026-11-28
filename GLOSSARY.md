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

**Opening screen**:
The page the phone app opens on, as set on the phone: Scan or Inventory. Not the start screen shown while the app loads, and not Pairing on a phone not yet set up.
_Avoid_: Home screen, start screen

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
Stop accepting a device token or machine token. The record is kept; a device with no history can then be deleted.

**Delete**:
Remove a revoked device that has no history from the list for good. It can't be re-enabled; it pairs again as a new device.
_Avoid_: Remove, forget

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
A product not yet identified from a tag: added by hand, first seen by the AMS, or made from a catalog color put on the shopping list. The first scan of its tag, if any, fills it in.

**Default name**:
The name a product is given when first seen on a tag or in the AMS: its material and its color, such as PLA Basic #FF0000. A name a person typed is not one.

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

**Over-held**:
A spool whose holds, leaving out those of a Printing request, are more than its grams left.

**Short**:
How many grams of a filament choice its holds don't cover. On an over-held spool, its grams left go to the requests holding it in Active-tab order, so the later ones are short.
_Avoid_: Shortfall, missing

**Covered**:
A filament choice that is short 0 g.
_Avoid_: Fully held

**Shopping list**:
The products to buy, in the app.
_Avoid_: Home Assistant's shopping list (a separate list in Home Assistant)

**Shopping list item**:
One product on the shopping list, with the reasons it is there: low stock, print requests short of it, or added by hand. A product has at most one. A catalog color not yet owned goes on as a provisional product made from it.
_Avoid_: Order (that word is for buying)

**Suggestion**:
A Viewer's ask to put a product or catalog color on the shopping list. It counts toward nothing until an Editor or Admin adds it.
_Avoid_: Request (that word is for print requests). Not a likely-empty suggestion, which is the AMS's.

**Shopping list history**:
The record of what people did to a shopping list item: added, suggested, ordered, on order changed, dismissed, brought back, by whom and when. It is never edited.
_Avoid_: History on its own, event (that word is for a spool's event log)

**On order**:
How many spools of a shopping list item's product have been ordered and not yet received. Each spool of the product received counts as one arriving.

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

**Catalog name**:
A catalog color's name followed by its filament line's, such as Hot Pink PLA Basic. A product with its default name takes it when linked.

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
The queue of things a person has to settle: flagged events, unidentified tags, likely-empty suggestions and possible duplicates. Used for this queue only.

**Flagged event**:
An event that was recorded but needs a person to check it, such as Received on a spool that is already open.

**Accept**:
Confirm that a flagged event is right.
_Avoid_: Reviewed

**Dismiss**:
Set aside an unidentified tag or a likely-empty suggestion. On the shopping list, hide an item until more of its product is needed than when it was dismissed.

**Possible duplicate**:
A product made by a scan that may be the same as a provisional product made from a catalog color, put to a person in Review. **Same product** makes them one product; **Keep separate** leaves both.
_Avoid_: Possible match (that word is for similar in-stock colors)

**Bring back**:
Return an accepted or dismissed item to Review, or a dismissed item to the shopping list.

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

**Active-tab order**:
The order of open print requests on the Requests page's Active tab: Urgent, Normal, then No rush; then by needed-by date, earliest first and undated last; then oldest first.

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

### Notifications

**Notification**:
A message RollCall sends a person about something they chose to hear about, by email or to their phone.
_Avoid_: Alert. Not a Home Assistant event.

**Phone notification**:
A notification shown by the phone app, even while the app is closed. Only a user's phone gets them.
_Avoid_: Push (except for how it is delivered)

**Notification settings**:
A user's choice of which notifications they get, and how: by email, to their phone, or both.

### Releases

**Release**:
One version of all of RollCall, such as `1.4.0`: the phone app and the server, with its web app, built from the same commit and tested together, so any part of a release works with the rest of it. The scanner firmware joins once it exists. Up to `1.3.0`, a release was the phone app alone.
_Avoid_: App release, server release (there are no separate ones)

**Release candidate**:
A build of a release published for testing before its version's final release, with a version such as `1.4.0-rc.1`. Test phones and test servers take it; everyday phones and servers don't.
_Avoid_: RC (except in tags and versions), beta, prerelease (that is how GitHub marks it)

**Final release**:
The release of a version that every phone and server gets, such as `1.4.0`, built from its newest release candidate's commit once its release record is approved.
_Avoid_: Stable release, production release

**Test server**:
A RollCall server kept only for trying release candidates, running a copy of the real data with email, Home Assistant, printers and backups turned off, so testing never reaches the household.
_Avoid_: Staging, dev server

**Test phone**:
A phone, or an Android private space on one, that takes release candidates and is paired with the test server for good.
_Avoid_: Beta phone

**Release record**:
The issue that records one release, from its first release candidate to its final release: the checklist steps in scope, their results and the sign-off.
_Avoid_: Release check, release issue, release PR
