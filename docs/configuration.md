# Configuration

The server reads these settings from environment variables or a `.env` file in `server/` (never committed; `server/.env.example` is the starting point). Every setting is optional.

Settings marked **Yes** under "In the app" can also be set in the app: on the Settings page (Admin), or on the Devices page for printers. A value in `.env` is the starting value, and once an Admin saves a value in the app, the app's value wins (see [ADR 0007](adr/0007-app-settings-win-over-env.md)). Settings marked **No** live only in `.env`, because a mistake in them could lock the Admin out or open LAN-only routes to the internet.

## Keeping this table current

The pull request that adds, removes or changes a setting in `server/src/filament_tracker/config.py` updates this table in the same branch. `server/tests/test_configuration_doc.py` fails when the table and the server's settings disagree, both on which settings exist and on which ones the app can set.

## Settings

| Setting | Example | Purpose | In the app |
| --- | --- | --- | --- |
| `ADMIN_TOKEN` | random 32 bytes | Machine access for Home Assistant and scripts, from the LAN only. Machine tokens made in the app replace it, and it keeps working if set | No |
| `SETTINGS_KEY` | random 32 bytes, base64 | Encrypts the secrets stored in the app. Unset: a key file (`settings.key`) is created beside the database | No |
| `BAMBU_KDF_SALT` | hex string | The tag key-derivation constant, served to provisioned scanners. Never in the repo, never logged | Yes |
| `CF_ACCESS_CLIENT_ID`, `CF_ACCESS_CLIENT_SECRET` | `….access`; the secret as Cloudflare gives it: `cfast_` and 48 letters and digits (since 2026-08-26), or 32 to 128 letters and digits (older tokens) | A Cloudflare Access service token, handed to paired phones so the app passes Access away from home. Unset: none | Yes |
| `PRINTERS` | `[{"name": "P1S", "host": "192.168.1.40", "serial": "01P00A...", "access_code": "..."}]` | Printers to watch over MQTT, as a JSON list; each entry may also set `port` (default 8883). `host` and `port` may be an MQTT proxy's. Each serial must be unique | Yes, seeded once: each printer is added the first time the server sees it, then edited on the Devices page |
| `MQTT_URL`, `MQTT_USER`, `MQTT_PASSWORD` | `mqtt://homeassistant.local:1883` | Home Assistant's MQTT broker, for discovery and state publishing; `mqtts://` for TLS. Unset: nothing is published. The URL must not hold the password | Yes |
| `HA_DISCOVERY_PREFIX` | `homeassistant` | Home Assistant's MQTT discovery prefix; defaults to `homeassistant` | Yes |
| `HA_URL`, `HA_TOKEN` | `http://homeassistant.local:8123`, long-lived token | Home Assistant's address and a long-lived access token, for firing events. Unset: no events are fired. The URL must not hold a user name or password | Yes |
| `TZ` | `America/New_York` | The time zone for every time the web app shows, whatever the viewer's device uses, and for the nightly backup. An IANA name; defaults to `UTC` | Yes |
| `CATALOG_SYNC` | `weekly` | How often the catalog syncs from its two sources, the Open Filament Database (`api.openfilamentdatabase.org`) and BambuStudio's color code list on GitHub (`raw.githubusercontent.com`): `off`, `daily` or `weekly`, at 04:00 in `TZ` (Mondays for `weekly`). `off` contacts neither except when an Admin presses Refresh now; defaults to `daily` | Yes |
| `SIMILARITY_CUTOFF` | `10` | The largest ΔE (CIEDE2000, 0.5 to 50) at which an in-stock product counts as a similar in-stock color on the Catalog page; defaults to 10. Below 2 is barely visible; 2–10 is close; above 25 is clearly different | Yes |
| `STORE_ADDRESS` | `https://eu.store.bambulab.com` | The Bambu Lab store that Find in store searches, by Bambu code. An `https` address with no path, query or fragment; one trailing slash is dropped. Defaults to `https://us.store.bambulab.com`; the store picks a region from where the visitor is, so change it only if that goes wrong | Yes |
| `SMTP_HOST` | `smtp.example.com` | The mail server RollCall sends email through. Unset: email is off | Yes |
| `SMTP_PORT` | `465` | The mail server's port (1 to 65535); defaults to 587 | Yes |
| `SMTP_SECURITY` | `tls` | How the connection is encrypted: `starttls` (connect, then upgrade; the default), `tls` (TLS from the start, usually port 465) or `none`. Certificates are checked against the system's trusted ones | Yes |
| `SMTP_USER`, `SMTP_PASSWORD` | `rollcall@example.com`, the password | The mail server login. Unset user: no login. The password is stored encrypted, never returned or logged | Yes |
| `SMTP_FROM` | `RollCall <rollcall@example.com>` | The from address of every email, with or without a name. Unset: sending fails with "No from address is set" | Yes |
| `PUBLIC_URL` | `https://rollcall.example.com` | The address the family opens RollCall at, for links in emails. An `https` address with no path, query or fragment; one trailing slash is dropped. Unset: emails have no links. Links are never built from an incoming request's address | Yes |
| `FIREBASE_PROJECT_ID`, `FIREBASE_APP_ID`, `FIREBASE_API_KEY`, `FIREBASE_SENDER_ID` | `rollcall-12345`, `1:123456789012:android:0123456789abcdef`, `AIza…`, `123456789012` | The Firebase project's client settings, for phone notifications through Google's push service (FCM) to the `google` app flavor. Handed to signed-in users' phones, which start Firebase from them. Unset: phones use a UnifiedPush distributor such as ntfy. See [deploy.md, Firebase](deploy.md#firebase-optional) | Yes |
| `FIREBASE_SERVICE_ACCOUNT` | the service-account key file's JSON | The key the server sends FCM notifications with (HTTP v1 API). Needed, with the four above, for FCM. Stored encrypted, never returned or logged | Yes |
| `TRUSTED_NETWORKS` | `192.168.0.0/16,10.0.0.0/8` | LAN ranges allowed to use bearer tokens, scanner routes, the API docs and first-start setup; defaults to the private ranges | No |
| `FORWARDED_ALLOW_IPS` | `192.168.1.5` | Address of the reverse proxy whose `X-Forwarded-For` is trusted. Unset: none | No |
| `SESSION_DAYS` | `30` | How long a web sign-in lasts, in days (1 to 365); defaults to 30 | Yes |
| `COOKIE_SECURE` | `true` | Set `false` only to sign in over plain HTTP on the LAN during development; production is HTTPS. Defaults to `true` | No |
| `WEB_DIR` | `/app/web` | The built web app; defaults to `web/build` in a source checkout | No |
| `DATABASE_URL` | `sqlite:////data/filament.db` | The SQLite database; defaults to `data/filament.db` beside the server | No |
| `BACKUP_DIR` | `/backups` | Where the nightly backups go (03:00 in `TZ`, 14 kept). Unset: no backups (the Docker image sets it) | No |

The command-line tools read a few variables of their own, such as `FT_TOKEN` for the scan simulator. Those are not server settings; see `server/README.md`.
