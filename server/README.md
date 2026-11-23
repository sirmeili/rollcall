# RollCall server

The FastAPI server for RollCall, and the Docker image it ships in. See the [repository README](../README.md) for the project overview.

## Development

The server needs Python 3.12 and [uv](https://docs.astral.sh/uv/). Run these from `server/` before requesting a review. CI runs the same checks on every PR that changes `server/`, and on every merge to `main`. From the repo root, add `--directory server` after `uv run` (for example `uv run --directory server pytest`), or `uv sync --directory server`.

```sh
uv sync                        # Install dependencies
uv run ruff check .            # Lint
uv run ruff format --check .   # Check formatting
uv run pytest                  # Run tests with the 90% coverage gate
```

Inner loop, with coverage off: `uv run pytest <test files> --no-cov`.

Changed-file coverage, without the 90% gate: `uv run pytest <test files> -o addopts="" --cov=<module> --cov-branch --cov-report=term-missing`, with one `--cov` per changed module (for example `--cov=filament_tracker.net`). Clearing `addopts` stops `pyproject.toml` from measuring the whole package.

Run the server with live reload: `uv run uvicorn filament_tracker.main:create_app --factory --reload`. It upgrades the database on startup; [Run it](#run-it) has the settings it needs.

**Migrations.** Apply them by hand with `uv run alembic upgrade head`. After changing `db/models.py`, create one with `uv run alembic revision --autogenerate -m "describe the change"`, then review the generated file. Never edit a migration that has been merged. `uv run alembic check` checks that the models and migrations match.

**Audit dependencies.** `uv export --quiet --no-hashes --no-emit-project -o requirements-audit.txt`, then `uv run pip-audit --disable-pip --no-deps -r requirements-audit.txt`. The exported file is ignored by git.

**Tools.** Each has its own section below.

- Accounts: `uv run ft-admin create-user <username> --role viewer|editor|admin [--requester]` (the password is prompted). Reset one with `uv run ft-admin reset-password <username>`. On a new database, first-start setup also creates the first Admin from the web app, with the setup code the server logs at start. See [Accounts](#accounts).
- Scan simulator: `uv run ft-sim scan <dump.bin|export.zip> --action lookup|received|opened|empty` and `uv run ft-sim generate <out.bin>`. `uv run ft-sim check-salt <dumps>` checks the key-derivation constant in use (saved on the Settings page, else `BAMBU_KDF_SALT`) against saved dumps without printing keys. It needs `FT_TOKEN` (a registered device token); see [Register a scanner](#register-a-scanner). Tag dumps never go in the repo.
- Real printer check: `uv run ft-printer check [--dump <dump.zip>] [--save captures/<name>.jsonl]`, using the printers saved in the app (or `PRINTERS` from `server/.env`); see [Check a real printer](#check-a-real-printer). Captures stay out of the repo.
- Home Assistant check: `uv run ft-ha check [--event]`, using the Home Assistant settings the server uses; see [Check against Home Assistant](#check-against-home-assistant). It prints counts and states only.
- Fake printer: `./fakeprinter/make-cert.sh`, then `docker compose -f fakeprinter/compose.yaml up -d --wait`, then `uv run ft-fakeprinter --serial FAKE01 --report tests/printer/reports/pushall.json` with `FT_ACCESS_CODE=fake-access-code`. Set `FT_FAKE_BROKER=127.0.0.1:8883` and `FT_HA_BROKER=127.0.0.1:11883` to include the printer and Home Assistant broker tests in `uv run pytest`; see [Fake printer](#fake-printer).

## Docker

Run these from the repository root (Docker with Compose v2). CI runs the same checks on every PR that changes the image (`Dockerfile`, `.dockerignore`, `server/`, `web/` or `deploy/`), and builds, checks and publishes the image on every merge to `main`.

- Build the image: `docker build -t rollcall:test .`
- Run the end-to-end test stack against it: from `server/`, `FT_COMPOSE_STACK=1 uv run pytest tests/deploy --no-cov` (it starts `deploy/test/compose.yaml` and removes it with its volumes).
- Scan the image before changing a base image digest: `docker scout cves --only-severity critical,high rollcall:test`. New base images follow the same rules as other dependencies (see [CODING_STANDARDS.md](../CODING_STANDARDS.md#dependencies)).
- Make a backup now: `uv run ft-admin backup` (needs `BACKUP_DIR`), or `docker compose exec rollcall ft-admin backup` on the server. See [Backups](#backups).

To run it on a server, see [docs/deploy.md](../docs/deploy.md).

## Run it

From `server/`, set an admin token and start the server. It creates and migrates its SQLite database in `data/` on startup.

```powershell
$env:ADMIN_TOKEN = "choose-a-long-random-value"
uv run uvicorn filament_tracker.main:create_app --factory
```

This listens on `127.0.0.1` only, so other machines cannot reach it. For scanners and the phone app, which connect over the LAN, add `--host 0.0.0.0`:

```powershell
uv run uvicorn filament_tracker.main:create_app --factory --host 0.0.0.0
```

Settings can also go in `server/.env`; copy [`.env.example`](.env.example), which lists every one. `.env` is never committed.

If the web app has been built (`npm ci` and `npm run build` in `web/`), it is served at `http://localhost:8000/`; set `WEB_DIR` to serve a build from elsewhere. The API is under `http://localhost:8000/api/v1`, with interactive docs at `http://localhost:8000/docs`. The docs, the scanner routes and bearer tokens (device and admin) work only from the LAN (`TRUSTED_NETWORKS`, by default the private address ranges); from anywhere else they get 404 or 403.

## Accounts

The web app has no default account. Until an Admin exists, the server is open for **first-start setup**: each time it starts, it writes a new setup code to its log, like this:

```text
First-start setup is open. Open the web app from your LAN and enter the setup code: K7QM-X3RD-9PTA
```

Open the web app from the LAN; it shows a Setup page instead of the sign-in page. Enter the code, a username and a password (at least 12 characters), and, if `.env` does not set them, the time zone and the tag key constant (both optional, and both can be set later on the Settings page). Setup creates the Admin, signs them in and closes for good. Setup answers only from `TRUSTED_NETWORKS`, so it cannot be reached through the reverse proxy, and five wrong codes in 15 minutes lock it for a while. A restart makes a new code, and the old one stops working.

Or create the first Admin from `server/` instead, which also closes setup; the password is prompted, at least 12 characters:

```powershell
uv run ft-admin create-user frank --role admin
```

Admins add more users on the Users page or through the API (`/api/v1/users`). **Requester** is a permission on top of any role, not a role: a Requester submits print requests and edits their own while they are Submitted. Give it on the Users page, or when creating a user from the command line:

```powershell
uv run ft-admin create-user sam --role viewer --requester
```

If every Admin is locked out, `uv run ft-admin reset-password <username>` sets a new password and signs that user out everywhere.

To sign in from PowerShell (the browser app comes later in M2):

```powershell
$body = '{"username": "frank", "password": "your password"}'
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/auth/login -SessionVariable web `
    -Headers @{ "X-Requested-With" = "filament-tracker" } -ContentType application/json -Body $body
Invoke-RestMethod -Uri http://localhost:8000/api/v1/auth/me -WebSession $web
```

The session cookie is marked Secure. Browsers accept it over plain HTTP on `localhost`, but from another machine on the LAN over plain HTTP set `$env:COOKIE_SECURE = "false"` before starting the server (development only). Requests that change something with the cookie must send the `X-Requested-With: filament-tracker` header. Five failed sign-ins for one username, or twenty from one address, within 15 minutes give HTTP 429.

## Backups

With `BACKUP_DIR` set, the server copies its database there every night at 03:00 in its time zone (the one saved on the Settings page, else `TZ`), using SQLite's online backup, and keeps the newest 14. Files are named by their UTC time, like `filament-20261110T090000Z.db`. The settings key is never copied into them. `uv run ft-admin backup` makes one at once. The Docker image sets `BACKUP_DIR=/backups`; see [docs/deploy.md](../docs/deploy.md) for restoring one.

Backups hold the database only. The model files and photos uploaded with print requests are kept beside the database, in a `request-files` folder next to the database file (`/data/request-files` in the Docker image), each under a random name ([ADR 0018](../docs/adr/0018-request-photos-are-files-beside-model-files.md)); [docs/deploy.md](../docs/deploy.md) shows how to copy them. A file or photo uploaded but never saved with a request is deleted once it is a day old, the next time anyone uploads one of the same kind.

## Catalog

The server keeps a local **catalog** of Bambu Lab's colors, copied from the Open Filament Database (OFDB, MIT license), and a copy of BambuStudio's color code list (AGPL-3.0, downloaded, never stored in this repo), for the Catalog page (`GET /api/v1/catalog`, any signed-in user). The Settings page's Catalog card (Admin) sets the schedule, the similarity cutoff and the Store address, shows each source's last successful sync, last attempt and its result, and OFDB's dataset version (`GET /api/v1/catalog/sync`), and has **Refresh now** (`POST /api/v1/catalog/sync`).

- **Schedule**: `CATALOG_SYNC` is `daily` (the default) at 04:00 in the server's time zone, after the 03:00 backup; `weekly` at 04:00 on Mondays; or `off`. One run syncs both sources. A new install, or one whose BambuStudio list has never synced, syncs about a minute after it starts, unless syncing is off. A failure is retried at the next scheduled run. Changing it on the Settings page applies without a restart.
- **Bambu codes**: a catalog color's Bambu code is the article number on its OFDB sizes; a color whose sizes have none, or disagree, has none.
- **Catalog links**: each product can be linked to its catalog color. At the end of every run, whatever each source's result, and when a scan creates a product or fills in a provisional one, a product's tag IDs are looked up in BambuStudio's list (material ID `GFA00` and variant ID `A00-K0` are filament ID `GFA00` with BambuStudio color code `K0`), and that entry's Bambu code gives the catalog color. No entry, two entries, or a code no catalog color has, leaves no automatic link; names are never compared. Editors set or clear a manual link with the product update (`PATCH /api/v1/products/{id}`, `catalog_color`); a manual link wins, a sync never replaces it, and it follows OFDB's merges (`moved_from`). One whose color has left the catalog is kept as "No longer in the catalog". Links store OFDB's UUIDs ([ADR 0016](../docs/adr/0016-catalog-links-use-ofdb-uuids.md)).
- **Owned**: a catalog color is owned when a product linked to it has a Sealed or Open spool. Owned is worked out on each read, never stored.
- **Similar in-stock colors**: expanding a catalog color lists the products with a Sealed or Open spool whose color is within `SIMILARITY_CUTOFF` (ΔE, CIEDE2000; default 10), in any material, closest first, leaving out the products linked to that color. A product of a different material (compared exactly, so PLA-CF is not PLA) carries a warning; a multi-color catalog color gets no comparison.
- **Find in store**: the catalog read carries `STORE_ADDRESS` (default `https://us.store.bambulab.com`), and the web app links to its search for a color's Bambu code.
- **Out of date**: after 14 days of failed OFDB syncs since its last success, the Catalog page says the catalog may be out of date. BambuStudio's list doesn't count: a stale copy only delays new automatic links.

- **What it contacts**: `https://api.openfilamentdatabase.org/json/all.json.gz` and `https://raw.githubusercontent.com/bambulab/BambuStudio/master/resources/profiles/BBL/filament/filaments_color_codes.json`, and nothing else; with `CATALOG_SYNC=off`, only when an Admin presses Refresh now. Each asks whether its file changed since the copy in use, so an unchanged file costs one small request ("Not modified").
- **Bambu Lab only**: other brands in the export are dropped.
- **Failures keep the last copy**: a network error, an incomplete download, bad JSON, a changed shape or a missing field is recorded for that source with a short reason, and its copy stays as it was. Each source succeeds or fails on its own. Failures show only on the Settings page's Catalog card and, after 14 days of OFDB failures, the Catalog page; never in Review or Home Assistant.
- **One at a time**: Refresh now while a sync is running is refused, and nothing new starts.
- **Inventory untouched**: catalog links are the only product data a sync changes; it never changes other product fields, spools, tags or events, and makes no Review item or Home Assistant event.

## Behind a reverse proxy

To reach the web app from outside, put it behind an HTTPS reverse proxy and tell the server the proxy's address, so it trusts the proxy's `X-Forwarded-For` header and no one else's:

```powershell
$env:FORWARDED_ALLOW_IPS = "192.168.1.5"   # the proxy
$env:TRUSTED_NETWORKS = "192.168.1.0/24"   # optional: narrow the LAN
```

uvicorn reads the same `FORWARDED_ALLOW_IPS` variable and applies the same rule, so it needs no extra options. Clients coming through the proxy from the internet can sign in and use the web app, but bearer tokens, scanner routes and the API docs are refused for them. Forward only the web app and `/api/v1` from the proxy anyway.

## Machine tokens

Home Assistant and scripts use a machine token. An Admin makes one in the **Machine tokens** card on the Settings page: give it a name and a role (Viewer, Editor or Admin), and copy the token, which is shown only once. The server keeps only a hash of it. Each token acts with its role, works only from the LAN (`TRUSTED_NETWORKS`), cannot act as a scanner, and is refused as soon as it is revoked. The card shows when each token was last used (saved at most once a minute). Send it as a bearer token:

```powershell
$headers = @{ Authorization = "Bearer $env:FT_MACHINE_TOKEN" }
Invoke-RestMethod -Uri http://localhost:8000/api/v1/inventory -Headers $headers
```

Give each script its own token with the lowest role that does the job, so one can be revoked without breaking the others. `ADMIN_TOKEN` from `.env` keeps working as an Admin token, for setups made before machine tokens.

## Register a scanner

Every scanner, including the simulator, needs its own token. Register one on the Devices page, or with an Admin machine token or the admin token as below; the token in the reply is shown only once.

```powershell
$headers = @{ Authorization = "Bearer $env:ADMIN_TOKEN" }
$device = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/devices `
    -Headers $headers -ContentType application/json -Body '{"id": "simulator", "name": "Simulator"}'
$env:FT_TOKEN = $device.token
$env:FT_DEVICE_ID = "simulator"
```

To revoke it later: `Invoke-RestMethod -Method Delete -Uri http://localhost:8000/api/v1/devices/simulator -Headers $headers`.

On the Devices page, registering a scanner or rotating its token also offers a QR code for the phone app, holding the server address and the token. The address defaults to the one in the browser and can be changed first.

## Tag key constant

Scanners and the phone app read tags with keys derived from each tag's UID and a published constant. The server keeps the constant (hex) in the **Scanners** group of the Settings page, stored encrypted, with `BAMBU_KDF_SALT` in `.env` as the starting value, and hands it to a device at `GET /api/v1/devices/provisioning` (device token, LAN only). It is not generated: it is the constant documented by the Bambu Research Group's RFID-Tag-Guide, and it is never committed. Save it on the Settings page (or put it in `.env`), then check the one in use against your own dumps, which still hold the real keys:

```powershell
uv run ft-sim check-salt C:\tag-dumps\*.zip
```

It prints how many of each dump's 16 sector keys the constant reproduces, and nothing else.

## Scan simulator

`ft-sim` sends scans exactly as a scanner would. It reads the server from `FT_SERVER` (default `http://localhost:8000`), the token from `FT_TOKEN` and the device ID from `FT_DEVICE_ID`.

Scan your own tags from BambuTagScanner exports (the ZIP from its Export button, or the `.bin` inside it). Keep dumps outside the repo: they contain tag UIDs and keys. The simulator drops the sector trailers, which hold the keys, before sending, and masks the tag UID in file names it prints.

```powershell
uv run ft-sim scan C:\tag-dumps\roll1.zip                      # lookup: what is this spool?
uv run ft-sim scan C:\tag-dumps\roll1.zip --action received    # New
uv run ft-sim scan C:\tag-dumps\*.zip --action received        # several at once
uv run ft-sim scan C:\tag-dumps\roll1.zip --action opened --at 2026-11-01T09:00:00-05:00
```

Without real dumps, generate synthetic tags. A generated file is one spool: scan the same file again to move it through its life.

```powershell
uv run ft-sim generate black.bin
uv run ft-sim generate white-matte.bin --color FFFFFFFF --detailed-type "PLA Matte"
uv run ft-sim scan black.bin --action opened
```

Each scan prints the feedback code, product, spool number (or "new spool"), state, the three soft-key choices and the suggested action. Add `--json` for the full server response, or `--event-id <uuid>` to resend the same event and test retries. Actions: `lookup` (default), `received`, `opened`, `empty`.

## Printers

The server watches each printer over MQTT and keeps the AMS slots and spools up to date. Admins add, edit, test and remove printers on the **Devices** page: a name, the address and port (default 8883), the serial and the access code, all on the printer's screen under the network settings. The access code is stored encrypted with the settings key and never shown again; leave its box empty when editing to keep it. **Test** connects once with the values in the boxes and says whether it worked. Saving reconnects only that printer, and removing one forgets it and its AMS slots (its events stay).

`PRINTERS` in `.env` can add printers too, as a JSON list (`port` is optional):

```powershell
$env:PRINTERS = '[{"name": "P1S", "host": "192.168.1.40", "serial": "01P00A123456789", "access_code": "12345678"}]'
```

Each serial is added once, the first time the server sees it; after that the printer is edited (or removed) in the app, and a restart does not bring it back. Put `PRINTERS` in `.env` rather than typing it into a shared shell: it holds the access code, and `.env` is never committed.

- **Certificate pin**: on the first connection the server stores the SHA-256 fingerprint of the printer's TLS certificate, and from then on talks only to that certificate. Changing the address keeps the pin. If the printer's certificate changes (for example after a firmware update), the printer shows a pin mismatch and an admin forgets the pin from the Devices page. **Test** checks the certificate against the pin before it sends the access code.
- **MQTT proxy**: to stay under the printer's connection limit, point `host` and `port` at a proxy such as `bambu-mqtt-proxy`, and use the proxy's alias as `serial` if it renames the printer. The pin is then the proxy's certificate.

## Home Assistant

The server publishes Home Assistant entities through MQTT discovery, under one device, **RollCall**:

- **Total spools** (sealed and open, not used up), **Total open** and **Total sealed**;
- **Low filament**: on while any product's sealed count is at or below its low-stock threshold (set on the Products page; 0 turns it off). Its `products` attribute lists the low products with their name, type, color, sealed count and threshold, and `count` says how many;
- **Spools in review**: the Review page's count: flagged events, unidentified tags, likely-empty suggestions and possible duplicates.

Entities from an earlier version of the server (such as per-product sensors) are removed automatically.

Set the broker on the **Settings** page (Admin), or in `server/.env`:

```sh
MQTT_URL=mqtt://homeassistant.local:1883   # Home Assistant's address, for the Mosquitto add-on
MQTT_USER=filament-tracker
MQTT_PASSWORD=...
```

- **The MQTT user**: the Mosquitto add-on accepts Home Assistant users (create one under Settings → People, for example `filament-tracker`) or the logins in the add-on's configuration.
- **Updates**: changes reach Home Assistant within about 5 seconds, whatever made them (a scanner, the phone, the web app or the printer).
- **Unavailable**: while the server is stopped or cannot reach the broker, the entities show as unavailable.
- **Home Assistant restarts**: everything is published again when Home Assistant restarts.
- **Status**: `GET /api/v1/health` reports the link as `off`, `connecting`, `connected` or `disconnected`.

The password is never logged or shown, and `MQTT_URL` must not contain it. Use `mqtts://` for a broker with a certificate the server's system trusts.

### Events for automations

With these set (on the Settings page or in `server/.env`), the server also fires Home Assistant events:

```sh
HA_URL=http://homeassistant.local:8123
HA_TOKEN=...   # a long-lived access token: your Home Assistant profile → Security
```

- `filament_tracker_spool_received`, `filament_tracker_spool_opened` and `filament_tracker_spool_emptied`, for every such action from any source, with the spool, product, type, color, new state, source and time in the event data.
- `filament_tracker_low_stock`, once when a product goes low, with its name, type, color, sealed count and threshold.

Only actions after the server starts are fired (a restart replays nothing), within about 5 seconds. An action undone before then is not fired. A failed request is retried three times and then dropped with a warning in the log; `GET /api/v1/health` reports events as `off`, `ready` or `failing`. The token is never logged, and redirects are not followed so it only goes to `HA_URL`.

To see them, open Developer tools → Events in Home Assistant, listen to `filament_tracker_low_stock` (or another), and record an action.

### The Settings page

Admins can set everything above on the **Settings** page, without restarting the server. The page also has a **General** group (the time zone every time in the web app is shown in, `TZ`, `UTC` by default; and how long a sign-in lasts, `SESSION_DAYS`, which applies from the next sign-in) and a **Scanners** group (the tag key constant), which work the same way:

- **Where values come from**: each one is labelled **From .env**, **Saved here** or **Default**. A value saved on the page is used instead of the `.env` one; **Use the .env value** goes back to it. An empty value saved on the page turns that setting off, even if `.env` sets it.
- **Passwords and tokens** are stored encrypted and never shown again. Leave the box empty to keep the saved one; **Clear** removes it.
- **Save** applies at once: the server reconnects to the broker and starts sending events with the new values.
- **Test** tries the values in the boxes (saved or not) once, and says only whether it worked: connected, unreachable, refused or an error.

Secrets are encrypted with a key from `SETTINGS_KEY`, or else from `data/settings.key`, which the server creates beside the database on first start. Back the key up with the database, or set `SETTINGS_KEY` instead, so the key is not stored next to the data it protects. A database restored without its key keeps everything except the saved secrets, which the Settings page then asks for again.

**Example automation**: [docs/home-assistant/low-stock-automation.yaml](../docs/home-assistant/low-stock-automation.yaml) adds a low product to Home Assistant's shopping list and notifies your phone. Paste it into a new automation's YAML editor, set your phone's notify action, save, and give it the `Claude` label. RollCall also has its own shopping list (the Shopping list page), which covers print requests short of filament as well as low stock, so you can keep either list or both.

## Check against Home Assistant

`ft-ha check` compares what the server published with what Home Assistant shows. It uses the settings the server uses (a value saved on the Settings page wins over `server/.env`), reading them from the server's database and key without changing either, so the server can keep running.

```powershell
uv run ft-ha check            # add --event to fire one filament_tracker_check event
```

- **Broker**: connects with the MQTT user, then lists the five discovery messages, any old ones still retained, availability, and the published totals and low filament.
- **Home Assistant**: checks the token, then shows each of the five entities and whether it matches what the broker holds. A value changed in the last few seconds may still be on its way; run it again.
- It prints counts and states only, never the broker or Home Assistant address, the user name, the password or the token. It exits with 1 when anything is marked as a problem.

Checklist before a release that changes the Home Assistant link:

1. `ft-ha check` passes with no problems.
2. In Home Assistant, Settings → Devices & services → Devices shows **RollCall** with its five entities.
3. Record an action (a scan, the phone or the web app): the totals change in Home Assistant within about 5 seconds.
4. Stop the server: the entities show as unavailable. Start it: they come back.
5. Restart Home Assistant: the entities come back with their values without restarting the server.
6. Developer tools → Events, listening to `filament_tracker_spool_opened` (and the others; the listener takes an exact event name, or `*` for every event, not a pattern such as `filament_tracker_*`): each action fires one event with the spool, product, color and source. `ft-ha check --event` fires `filament_tracker_check`.
7. Set a product's low-stock threshold to its sealed count: `filament_tracker_low_stock` fires once, Low filament turns on and lists it, and the example automation adds it to the shopping list and notifies the phone. Put the threshold back.
8. On the Settings page, **Test** reports both links working; with a wrong password typed in, it reports the broker refused it. **Save** a change and the link reconnects without a restart.

## Email

RollCall emails users through your mail provider's SMTP server. Set it in the **Email** group of the Settings page (Admin), or in `server/.env` (see [docs/configuration.md](../docs/configuration.md)): the host, port, security (`starttls`, `tls` or `none`), user, password and from address, and the Public URL that links in emails use. With no host, email is off.

- **Addresses**: each user adds their own address on the Account page, and an Admin can set anyone's on the Users page. Addresses are optional and never verified.
- **Notification settings**: each user chooses which notifications they get by email in the Notifications list on their Account page; nobody else can change them. The kinds a user can choose depend on their role and Requester (`notifications/kinds.py`), and one resolver (`notifications/recipients.py`) decides who is told: role, their choice or the default, a disabled account, and never about what they did themselves.
- **Low stock**: the database poll, which runs every 5 seconds whether or not Home Assistant is set up, emails once each time a product goes from not low to low stock, linking to Inventory searched for it. A restart tells nobody: the first poll after start only records which products are low.
- **Send test email** sends to the signed-in Admin's own address with the saved settings and shows the result. The server allows one test every 30 seconds.
- **In the background**: emails are handed to a background sender, so nothing waits for the mail server. A failed send is retried 3 times over about 15 minutes, then logged and dropped. Emails still waiting are lost on a restart. The Email group shows the last success and the last failure.
- The password is stored encrypted, and never shown or logged. Errors are short descriptions such as "The mail server refused the user name or password", never the mail server's own text.

## Phone notifications

The server also sends each notification to the phones of the people told about it: a Web Push (RFC 8030), encrypted for each phone (RFC 8291) and signed with the server's VAPID key (RFC 8292), carrying the kind, the email's subject and sentence, and the path of the page it is about. Each user chooses them with the Phone switch beside each Email switch in the Notifications list on Account; Phone is on by default for every kind their role can see. The same resolver as for email decides who is told.

- **Only a user's own phones**: a phone set up by signing in registers its push endpoint with the signed-in session (`PUT /api/v1/push/devices/{device_id}`, with the VAPID public key from `GET /api/v1/push/config`), from anywhere, not only the LAN. Only a phone that belongs to the signed-in user and isn't revoked is accepted; a shared phone, another user's or a revoked one answers 404, and a device token alone is refused. `DELETE` on the same path removes it. Revoking or unlinking a phone drops its endpoint, and a disabled user's phones get nothing.
- **The VAPID key pair** is made on first start and stored with the private key encrypted by the settings key, never shown or logged. It never changes. A database restored without its settings key can't open it: a new pair is made and every phone registers again.
- **In the background**: pushes are handed to a background sender after the change commits, so a push service that is down never fails a change. A 404 or 410 drops that phone's endpoint at once. Any other failure (a timeout, a 5xx, a 429) is retried 3 times over about 15 minutes, then given up and counted; a phone with no success in 30 days is then dropped. Pushes still waiting are lost on a restart. Each push lives a week at the push service, with normal urgency, and stays under 4 KB.
- **Test**: `POST /api/v1/push/devices/{device_id}/test` sends a test notification to the caller's own phone and says whether it went, at most once every 30 seconds per phone.
- Logs name the phone's device only, never its endpoint URL, its keys or what was sent.

## Fake printer

Test the printer link without a printer: a Mosquitto broker in Docker stands in for the printer's MQTT server, and `ft-fakeprinter` plays the printer on it. Needs Docker and `openssl`; run from `server/` in Git Bash or WSL for the first command.

```sh
./fakeprinter/make-cert.sh                                  # a throwaway certificate, never committed
docker compose -f fakeprinter/compose.yaml up -d --wait     # TLS on 127.0.0.1:8883, user bblp
```

```powershell
$env:FT_ACCESS_CODE = "fake-access-code"
uv run ft-fakeprinter --serial FAKE01 --report tests\printer\reports\pushall.json --then tests\printer\reports\remain-delta.json
```

It publishes the full report, then each `--then` change every 5 seconds (`--interval`), and answers every `pushall` with the full report until stopped with Ctrl+C. Point the server at it with:

```powershell
$env:PRINTERS = '[{"name": "Fake", "host": "127.0.0.1", "serial": "FAKE01", "access_code": "fake-access-code"}]'
```

The integration tests use the same broker: set `FT_FAKE_BROKER=127.0.0.1:8883` before `uv run pytest` to include them (CI does). The broker also listens for plain MQTT on `127.0.0.1:11883` (change it with `FAKE_HA_BROKER_PORT`), standing in for Home Assistant's broker: set `FT_HA_BROKER=127.0.0.1:11883` to include the Home Assistant broker tests. Stop it with `docker compose -f fakeprinter/compose.yaml down`.

## Check a real printer

`ft-printer check` connects to a printer once and prints what each AMS and AMS HT slot reports. It uses the printers saved in the app (read from the server's database and key, which it does not change), then any in `PRINTERS` not saved yet. It pins the certificate it finds for that connection only. Stop the server first if the printer is near its MQTT connection limit.

```powershell
uv run ft-printer check --dump C:\tag-dumps\spool.zip --save captures\p1s.jsonl
```

- `--dump` (one or more tag dumps) says whether each tag's tray UID or UID is what a slot reports. Tags are labelled by position and product, and no UID is printed.
- `--save` writes only the AMS parts of each message, with every tray UUID, tag UID and unit serial replaced. `captures/` is ignored by git; check a capture before using it as a test fixture.

Checklist before a release that changes the printer link:

1. `ft-printer check` lists every loaded slot with its material, color and remaining %, and the AMS HT as "AMS HT 1".
2. With a dump of a loaded spool, it reports that the tray UUID equals the tag's tray UID.
3. Start the server: Devices shows the printer Online with its certificate pinned and every slot.
4. A tagged spool loaded without a scan becomes Open, flagged for Review, and Spool detail shows "Loaded in".
5. Remaining % on Spool detail follows the AMS after a print.
6. Forget pin on Devices; the next connection pins the certificate again.
