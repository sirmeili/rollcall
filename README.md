# RollCall (formerly Filament Tracker)

A self-hosted system that tracks every Bambu Lab filament spool from delivery to empty, using the RFID tags already on the spools. Tap a spool on a small touchscreen scanner (or an Android phone running the companion app), confirm whether it is new, just opened or empty, and a central server keeps the inventory, feeds Home Assistant and serves a web app for a few users.

It runs in Docker with no Bambu cloud dependency. Scanners and integrations stay on your LAN; the web app, with personal accounts and Viewer, Editor and Admin roles, can be reached from the internet through your own HTTPS reverse proxy.

Planned next: two small changes (hiding revoked devices, #71, and the code rename, #72), then print requests (M10). With print requests, a co-owner of the printer submits models, picks filament from what is in stock or from the full Bambu catalog (from the Open Filament Database), and follows each print to pick-up, with filament held for accepted requests. The repo is `sirmeili/rollcall`; the code keeps its old `filament_tracker` names until the code rename.

> **Status: the server, web app and phone app are built; the scanner hardware is still to come.** Built (milestones M0a, M1, M2, M5, M6, M8 and M9): the server, with the tag decoder, the event log, the scanner API and a scan simulator; the web app, with personal accounts and Viewer, Editor and Admin roles, the Inventory, Spools, Spool detail, Products, Catalog, Requests, Review, Shopping list, Activity, Devices, Users, Account and Settings pages, and a phone layout; the printer link, which reads AMS and AMS HT slots over MQTT and has been checked against a real P1S; the Home Assistant link, with MQTT discovery entities, events and an example low-stock automation, checked against a real Home Assistant; the Android phone app, a scanner with an offline queue and a Delivery mode, where the phone's Back button (or swipe-back gesture) goes back a page, closes an open sheet, dialog or scan card first, and sends the app to the background from its opening screen, released through GitHub Releases for Obtainium in two flavors (`google`, and `foss` with no Google code) and checked on a Pixel 9 Pro XL; and deployment, with printers, machine tokens and first-start setup in the app, one Docker image (`ghcr.io/sirmeili/rollcall`) run with Docker Compose, and nightly backups, emailing Admins who choose it when one fails (see [docs/deploy.md](docs/deploy.md)). Leaving a form with unsaved changes asks first, in a browser and on the phone, and a saved form or finished pairing is replaced in history by the page it opens, so Back never returns to it. The Catalog page lists every Bambu Lab color from a local copy of the Open Filament Database, with each color's Bambu code from BambuStudio's color code list, which colors are owned, and a Find in store link; the Products page shows which catalog color each product is, linked from its tag's Bambu code or by hand. Each spool keeps its grams: its net weight, from its tag or else its catalog color's size, and about how many grams are left, which the AMS's remaining % keeps up to date and an Admin can set by hand on Spool detail. Print requests have begun: Requester is a permission on any account, and a Requester submits and edits print requests, each with a model file or link, its filament choices from what is in stock or the catalog, a needed-by date and a priority; Editors and Admins see every request and change its priority while it is open, and an Admin approves a Submitted request, giving the grams each filament choice needs, or rejects it with a reason. Approving holds those grams on spools of the chosen filament (part-used spools first), so the same grams are never promised twice, and the request moves on by itself to Queued, or to Waiting on Filament when a choice is short; Editors and Admins see each choice's holds and shortfall, and the requester sees whether each is held or waiting (a Queued request always reads as held). A waiting request takes more filament by itself whenever stock changes (a spool received, opened, emptied or undone, an AMS report, a hand edit of grams, a catalog link, or holds released), the most pressing request first, and moves to Queued once every choice is held; a spool that is emptied or undone releases its holds, and a Queued request left short shows by how much. When a spool has less left than its requests hold, its grams go to them most pressing first, so the later ones show as short. An Admin can change a request's holds by hand while it is Approved, Waiting on Filament or Queued: new grams for a choice, another spool or other grams for a hold (a similar color's spool too), or no hold; the request is checked again, the change shows in its history (as "Filament updated" to the requester), and no email is sent. Inventory and the request form's filament picker show about how many grams of each product are available (not held), and Spool detail shows a spool's held and available grams, flags a spool held beyond its grams left, and lists the requests holding it for Editors and Admins. An Admin then moves it along by hand through Queued, Printing, and Done or Failed, and reprints a Failed one as another attempt of the same request, giving its grams again (the last attempt's filled in) and holding them, so it lands on Queued or on Waiting on Filament; Done, Failed and Cancelled release a request's holds, so their grams are available again; an Admin adds up to 4 photos of the finished print in the Done move or later, which the requester sees on the request; the requester or an Admin marks a Done request Picked Up; the requester cancels their request before it starts printing, and an Admin cancels one before then, or once it fails, with a reason. The Requests page splits active requests from closed ones, and Editors and Admins can filter the active ones by status and, if they are also Requesters, show only their own. With email set up on the Settings page, a requester is emailed when an Admin approves (saying whether it's queued or waiting on filament), rejects, prints, finishes, fails or cancels their request, or it starts waiting on filament, with the photos in the email when it is done and in another email when a photo is added later, and Admins are emailed about each new request (Editors can choose to be too); anyone can choose an email when a product becomes low stock (noticed whether or not Home Assistant is set up), which opens Inventory searched for it, and when a spool in an AMS is nearly out, which opens the spool; each person chooses which of these they get by email in the Notifications list on Account. Each can also be a phone notification, sent by the server as a Web Push (or an FCM message) to each of a user's own phones that registered for them, chosen with a Phone switch beside each Email switch and on by default; a user's phone (not a shared one) registers for them through a UnifiedPush distributor such as ntfy once signed in, or, in the `google` flavor, through Google's push service (FCM) when the owner has set up Firebase on the Settings page, shows each kind in its own Android notification channel, and opens a tapped one's page; it asks once for Android's permission to show them, says on Pairing whether they work there and by which route (or how to allow them, or to install ntfy) with Send a test notification, and stops them on Unlink and sign-out, away from home too. The shopping list (spec #78) is built: every role sees it, and each low-stock product is on it as one item needing enough spools to stop being low (its threshold minus its Sealed spools, plus one), grouped by the filament line of its catalog link, with each line's total and a Find in store link, then the products not in the catalog. Approved print requests short of filament put it on the list too, their grams added up and rounded up to spools once by the item's size (the one an Editor or Admin chose, else the last spool's net weight, else the catalog's), and approving a catalog color nobody owns makes its "From the catalog" product; each request is named only for people who may see it. Editors and Admins add spools to it by hand, from the list or a Catalog color row, and remove them again; a catalog color nobody owns goes on as a "From the catalog" product, which the first scan of its tag fills in, and each item shows its recent shopping list history. Viewers suggest a product or a catalog color the same way: suggestions wait at the top of the list, counting toward nothing, until an Editor or Admin adds one (only then making a catalog color's "From the catalog" product) or dismisses it, and the Shopping list link shows how many are open; Editors and Admins can choose to be emailed about each new suggestion. When a scan can't be sure, Review asks whether the new product is a possible duplicate of a "From the catalog" product of the same filament line with a close color: Same product makes them one, keeping the scanned product and moving its link, threshold, on order, reasons, suggestions and dismissal onto it, and Keep separate leaves both. Each item shows what to buy: its need minus what is on order. Editors and Admins mark an item Ordered or set its on order by hand, each spool of the product takes one off on order the first time it appears in stock, and a fully ordered item stays in its line under an On order label. Dismissing an item removes its hand-added spools and hides it until more of it is needed than when it was dismissed; it then comes back marked with how many more, and the Dismissed filter lists the rest, with Bring back. A request's short choice shows its product's item stage to anyone who can see the request: On the shopping list, Partly ordered (n of m spools ordered) or Ordered, linked to the item. Not built yet: the scanner firmware and hardware. What comes next, in order, is in the [Roadmap](https://github.com/sirmeili/rollcall/issues/69) issue.

[![Filament scanner case](hardware/enclosure/preview.png)](https://sirmeili.github.io/3d-mockup-viewer/openscad/viewer.html?manifest=https://raw.githubusercontent.com/sirmeili/rollcall/main/hardware/enclosure/manifest.json)

## Goals

- See at a glance how many sealed and open spools exist for each filament (for example: Black PLA Basic, 3 sealed, 1 open).
- Record each spool's lifecycle with one tap and one confirm: New, Opened, Empty.
- Identify spools from their Bambu RFID tags, with no manual typing of type or color.
- Use P1S/AMS telemetry to fill in what the printer already knows: when a spool was first loaded and its remaining %.
- Surface low-stock alerts and inventory sensors in Home Assistant.

Writing or cloning tags, load-cell weighing, third-party filament without Bambu tags and slicer integration are out of scope for v1.

## How it works

1. **Tap.** The scanner reads the tag and asks the server what it knows about the spool.
2. **Confirm.** The screen shows the product, a color swatch and the current state, and highlights the suggested action. Confirm with one of the three buttons or by touch.
3. **Record.** The server logs the event and updates the inventory. If the server is unreachable, the scanner queues the event and retries.

Each spool carries two tags with different UIDs but the same tray UID. The tray UID is the spool's identity, so either tag works.

## Components

| Component | Role | Planned stack |
| --- | --- | --- |
| Scanner | Reads tags, derives keys and posts raw tag data; shows the spool and takes the action | ESP32 "Cheap Yellow Display", PN532 reader, three soft-key buttons; PlatformIO, Arduino, LVGL |
| Phone scanner | An Android phone as a scanner (on phones whose NFC supports MIFARE Classic), plus the full web app; set up by signing in (or paired by a QR code from the Devices page) | Capacitor around the web app, with a Kotlin NFC plugin |
| Server | Decodes tags, stores every change as an immutable event, derives spool state and serves the API | Python 3.12, FastAPI, SQLAlchemy, SQLite, Alembic |
| Web UI | Check stock, fix mistakes and manage products, devices and users | SvelteKit (TypeScript), built to static files served by the server |
| Printer link | Reads AMS trays read-only to detect opened spools and track remaining % | Local MQTT from the P1S |
| Home Assistant | Inventory and low-stock entities, plus events for automations | MQTT discovery, REST API |
| Scan simulator | Replays saved tag dumps so the server can be tested without hardware | Python |
| Screen simulator | Runs the real scanner screens on a PC, with the keyboard as buttons | LVGL |
| Fake printer | Replays AMS report messages over TLS so the printer link can be tested without a printer | MQTT |

## Enclosure

The scanner case is a parametric OpenSCAD model with the screen and buttons on the front and a flat "tap here" zone over the PN532 antenna. It holds the CYD, the PN532, the button board, a speaker and a USB-C power input. It is designed to mount on a wall by keyhole screws, magnets or Command strips, and can also sit on a shelf.

Select the image above to open the interactive 3D mockup. The source is in [hardware/enclosure/](hardware/enclosure/):

- [filament-scanner-case.scad](hardware/enclosure/filament-scanner-case.scad): the OpenSCAD model
- [manifest.json](hardware/enclosure/manifest.json): the part list and groups for the mockup viewer
- [preview.png](hardware/enclosure/preview.png): the rendered preview

## Roadmap

The [Roadmap](https://github.com/sirmeili/rollcall/issues/69) issue lists the planned work in order, one sub-issue per piece. In outline:

| Milestone | Scope | Status |
| --- | --- | --- |
| M0a Prove reading, phone | Dump two rolls of the same product with an Android app; confirm matching product fields and distinct tray UIDs; try reading through the shipping box | Built |
| M1 Server core | Decoder, data model, event log, `/scans` API, scan simulator, tests | Built |
| M2 Web UI | User accounts and roles, inventory, spools, spool detail, products, review, activity, devices, users, manual entry | Built |
| M5 Printer link | P1S MQTT ingest, automatic Opened, remaining %, likely-empty suggestions | Built |
| M8 Phone scanner | Android app (Capacitor around the web app, Kotlin NFC plugin), QR pairing, offline queue | Built |
| M6 Home Assistant | MQTT discovery entities, events, low-stock automation, the Settings page with the Home Assistant settings | Built |
| M9 Deployment | Printers and the remaining settings in the app, machine tokens, first-start setup, Docker image and Compose file, nightly backups | Built |
| Small changes | The Android Back button (#70, built), hiding revoked devices (#71), the code rename (#72) | In progress |
| M10 Print requests, Phase 2 | Filament catalog and Bambu color codes, the Requester role, print requests and their status pipeline, holding filament, shopping list | In progress |
| M11 Print requests, Phase 3 | Reading 3MF files, print jobs from the printer, push notifications, picking colors on the model, MCP server | Planned |
| M3a Firmware without hardware | Scan flow, offline queue and dedupe logic with PC tests, screen simulator | Planned |
| M0b Prove reading, PN532 | Repeat the read tests on the bench rig; measure reading through the lid and shipping box | Planned |
| M3b Firmware on hardware | Breadboard build, real drivers, provisioning, OTA | Planned |
| M4 Enclosure | Printed case, button labels, antenna placement, final wiring | Planned |
| M7 Later | Asking RollCall questions, spool lifecycle stats, a custom PCB scanner, a load-cell scale, Spoolman sync, untagged filament, a second scanner by the printer | Planned |
| Spec audit | Checking the archived v1 spec against the tests | Planned |

## Repository layout

```text
AGENTS.md                     Rules for AI agents working in this repo
CODING_STANDARDS.md           The rules every change follows: modularity, tests and coverage, dependencies, secrets
GLOSSARY.md                   The domain language: spools, tags, states, events and the rest
docs/adr/                     Architecture decision records: why the hard-to-reverse choices were made
docs/configuration.md         Every setting, its default and where it is set
docs/testing.md               Test layers, coverage exclusions and the manual checklists
docs/releasing.md             Releasing the phone app: versions, release candidates, the scoped checklist and the release record
docs/deploy.md                Running RollCall with Docker Compose or Portainer: setup, proxy, Cloudflare Tunnel, backups, updates
docs/home-assistant/          Example Home Assistant automation
docs/mockups/web/             Web app page mockups and design tokens
docs/mockups/mobile-scanner/  Phone app Scan screen mockups
docs/mockups/mobile-web/      Phone layout mockups: bottom bar, menu, Account, Inventory
docs/mockups/logo/            The RollCall logo and its animations
docs/agents/                  Issue tracker, triage labels and domain docs settings for the agent skills
docs/archive/                 The retired v1 specification, kept as background reading
hardware/BOM.md               Bill of materials for one scanner
hardware/enclosure/           3D model of the scanner case
server/                       FastAPI server: decoder, database, event log, API, scan simulator
web/                          SvelteKit web app (TypeScript), built to static files the server serves
android/                      Android phone app: Capacitor around the web app, Kotlin NFC plugin
Dockerfile                    The image: the web app built with Node, served by the Python server
deploy/                       Compose file and example settings for the home server; deploy/test/ is the end-to-end test stack
.github/workflows/            CI: lint, tests, 90% coverage gates, dependency audits, end-to-end tests, a check for links to retired docs; the image build, test and publish; phone app releases. On a pull request, jobs for areas it does not change are skipped; `ci-ok` and `image-ok` are the checks `main` requires
.github/ISSUE_TEMPLATE/       The release record issue template
```

## Documentation

Planned work is described in GitHub issues, starting from the [Roadmap](https://github.com/sirmeili/rollcall/issues/69). For what is built, the code and its tests are the record, with the domain language in [GLOSSARY.md](GLOSSARY.md), the reasons behind the main choices in [docs/adr/](docs/adr/), the rules for changes in [CODING_STANDARDS.md](CODING_STANDARDS.md), the settings in [docs/configuration.md](docs/configuration.md), and the test layers and checklists in [docs/testing.md](docs/testing.md). The v1 specification, retired in November 2026, is kept as background in [docs/archive/SPEC-v1.md](docs/archive/SPEC-v1.md).

Secrets such as the tag key-derivation constant, tokens and the printer access code are supplied as configuration and are never committed.

## Development

Text files are checked out with LF line endings on every platform (`.bat` and `.cmd` files with CRLF), as set in [.gitattributes](.gitattributes). A Windows clone made before that file was added may still hold CRLF files; fix it once, from the repository root. **This throws away all uncommitted work**, so commit or stash it first:

```sh
git rm --cached -r .
git reset --hard
```

Each area's README lists all its commands, including the checks to run before a review and the inner-loop test command to run after each edit: [server/README.md](server/README.md) (with the Docker image), [web/README.md](web/README.md) and [android/README.md](android/README.md). The basics:

The server needs Python 3.12 and [uv](https://docs.astral.sh/uv/). From `server/`:

```sh
uv sync                # Install dependencies
uv run pytest          # Run tests with the 90% coverage gate
uv run ruff check .    # Lint
uv run uvicorn filament_tracker.main:create_app --factory --reload
```

The web app needs Node.js 24. From `web/`:

```sh
npm ci                 # Install dependencies
npm run test:coverage  # Run tests with the 90% coverage gate
npm run build          # Build to web/build, which the server serves at /
```

The Android app needs JDK 21 and the Android SDK (Android Studio installs it). From `web/`, then `android/`:

```sh
npm run build && npx cap sync android   # Copy the web app into the Android project
./gradlew coverageCheck                 # Kotlin tests of both flavors with the 90% coverage gate
./gradlew assembleDebug                 # Build app/build/outputs/apk/<flavor>/debug/app-<flavor>-debug.apk
```

The app comes in two flavors, released together: `google`, for phones with Google Play, and `foss`, with no Google code; [android/README.md](android/README.md#flavors) says which to pick. To install the app on a phone (releases through GitHub Releases and Obtainium, or a development build), run a phone test or read the phone checklist, see [android/README.md](android/README.md). To make a release, through release candidates on test phones and a signed-off release record, follow [docs/releasing.md](docs/releasing.md).

To build and run the Docker image, from the repository root:

```sh
docker build -t rollcall:test .
cd server && FT_COMPOSE_STACK=1 uv run pytest tests/deploy --no-cov   # The end-to-end test stack
```

To run it on a server, see [docs/deploy.md](docs/deploy.md).

To create accounts (`ft-admin`), run behind a reverse proxy, register a scanner and use the scan simulator (`ft-sim`) with your own tag dumps, see [server/README.md](server/README.md).

The server keeps its SQLite database in `server/data/` by default (set `DATABASE_URL` to change it) and applies migrations on startup.
