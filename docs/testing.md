# Testing

The server is fully testable without hardware. Firmware logic is unit tested on a PC, and hardware behaviour gets a short manual checklist. The PR that adds a test layer, changes a coverage exclusion or moves a checklist updates this page.

## Test layers

| Layer | What is tested | How |
| --- | --- | --- |
| Decoder | Every field; two spools of the same product yield the same product key | pytest against generated tags in CI, plus own spools and the public Bambu RFID library locally |
| State machine | Every transition in the table, out-of-order flags, undo | pytest, property tests for event replay |
| API | Auth on every route, idempotent scans, validation errors | pytest with FastAPI TestClient |
| Hold service | Where holds go (Open spools first, least grams left first, then Sealed), splitting, partial cover, skipped unknown spools, shortfalls (an over-held spool's grams left shared among its holders in the order given, a holder left out taking none) and available grams, per spool and per product, and over-held (leaving out the holders the caller names) | pytest calling Inventory's hold service directly |
| Module boundary | Inventory never imports Print Requests (ADR-0014); two older imports, in `db/models.py` and `api/auth.py`, are allowed by name | pytest reading each Inventory module's imports |
| Security | Setup refused from outside the LAN, with a wrong code or once an admin exists; stored secrets never returned or logged, and unreadable without the key; machine tokens limited to their role and refused once revoked; unauthenticated access refused, role checked on every route, revoked tokens and ended sessions refused, sign-in throttling, bearer tokens refused from outside the LAN, CSRF header, security headers, oversized payloads rejected; print requests: only Requesters submit and edit, another user's request answers 404, Editors change only the priority, only the people the pipeline names move a request (tokens below Admin are refused), model files checked by their content and downloaded as attachments that browsers never run, Approve's grams only from an Admin, a request's grams, shortfall, holds and available grams shown only to Editors and Admins (a requester sees only whether each choice is held), the requests holding a spool never shown to Requesters, Viewers or tokens below Editor, holds changed (a choice's grams, a hold added, changed or removed) only by a signed-in Admin, photos uploaded, added and removed only by a signed-in Admin, stopped at 20 MB, and served only as `image/jpeg` or `image/png` with `nosniff`; email: the Email settings and Send test email Admin only, Send test email only for a signed-in Admin and at most once every 30 seconds per server, the SMTP password never returned or logged, a user edits only their own address and email switches, links in emails never built from the request's Host header | pytest security suite, run in CI |
| Web app | Components, API client, role-based visibility | Vitest with Testing Library; 90% coverage; `svelte-check` and `npm audit` in CI |
| Web end to end | Sign in as each role, inventory, record and undo an action, review | Playwright against the real server with a database seeded by the scan simulator |
| Phone app | Scan flow, offline queue, on-phone decode, pairing | Vitest; 90% coverage |
| Phone NFC plugin | Key derivation (matching the server), block assembly, trailer stripping, encrypted storage | Kotlin unit tests with a fake tag; 90% line coverage (JaCoCo), excluding the Android glue that needs a phone (see [Coverage exclusions](#coverage-exclusions)) |
| Phone on hardware | Reading on a real phone, MIFARE Classic detection, QR pairing, offline queue, sign-in | Manual checklist per release |
| AMS ingest | Report messages produce the right events | Fake printer replaying recorded or documentation-based messages, including a report captured from a P1S with its identifiers replaced |
| Printer on hardware | Connection and pin, every AMS and AMS HT slot, tray UID matching a scanned tag, automatic Opened, remaining % | `ft-printer check` and a manual checklist, before a release that changes the printer link |
| Home Assistant on hardware | The five entities and their values, unavailable on stop, back after a Home Assistant restart, events, the low-stock automation, the Settings page Test and Save | `ft-ha check` and a manual checklist, before a release that changes the Home Assistant link |
| End to end | Scan simulator drives Received, Opened, Empty for a spool; HA entities update | Docker Compose test stack with a Mosquitto container |
| Firmware logic | Screen flow, tag parsing, offline queue, dedupe, button thresholds | PC unit tests with fakes; 90% coverage, excluding a named list of hardware drivers |
| Firmware screens | Every screen and soft-key mapping | Screen simulator |
| Firmware on hardware | Read through lid and box, each soft key and touch target, menu navigation, timeout, offline queue, OTA, plus the excluded drivers | Manual checklist per release |

## Coverage exclusions

Every automated layer with a coverage gate holds 90%. Code is excluded only when it cannot run without real hardware, and each exclusion is covered by a manual checklist instead.

**Phone NFC plugin.** The JaCoCo gate in [`android/app/build.gradle`](../android/app/build.gradle) (`coverageExcludes`) leaves out the Android glue that needs a phone, which the [phone checklist](#manual-checklists) covers:

| Excluded | Why it needs a phone |
| --- | --- |
| `FilamentTrackerPlugin` | NFC reader mode, the camera and Capacitor calls |
| `AndroidMifare` | The MIFARE Classic adapter over Android's NFC API |
| `KeystoreKey` | Android Keystore storage |
| `PrefsValues` | SharedPreferences storage |
| `MainActivity` | The Android activity |

It also leaves out generated classes (`R`, `BuildConfig`, `Manifest`), which hold no logic.

**Firmware.** Firmware logic is gated at 90% in its PC unit tests, excluding a named list of hardware drivers, which the firmware checklist covers. The firmware is not built yet, so neither the list nor the gate is configured; the firmware milestone that adds them names the drivers here.

## Manual checklists

| Checklist | When it runs | Where it lives |
| --- | --- | --- |
| Phone on hardware | Before a release that changes the phone app | [android/README.md, Checklist](../android/README.md#checklist) |
| Printer on hardware | Before a release that changes the printer link | [server/README.md, Check a real printer](../server/README.md#check-a-real-printer) |
| Home Assistant on hardware | Before a release that changes the Home Assistant link | [server/README.md, Check against Home Assistant](../server/README.md#check-against-home-assistant) |
| Firmware on hardware | Before each firmware release | Not written yet; it comes with the firmware on real hardware |

## Tag dumps and captures

Public and personal tag dumps contain tag UIDs and keys. Printer captures (`ft-printer check --save`) have their identifiers replaced. Both are used locally and never stored in the repo: `.gitignore` leaves out dump files, `tag-dumps/` and `server/captures/`. A capture becomes a test fixture only after it has been checked by hand. CI uses generated tags only.
