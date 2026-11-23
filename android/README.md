# RollCall Android app

The phone app: a Capacitor wrapper around the web app in `web/`, with a Kotlin plugin for NFC tag reading, QR scanning, phone notifications and Keystore storage, and Capacitor's official App plugin for the Back button and sending the app to the background. It works only on phones whose NFC chip reads MIFARE Classic, such as Google Pixel phones. See ADR-0010 (`docs/adr/0010-phone-app-capacitor-and-kotlin-nfc.md`) for why it is built this way.

## Build

The build needs JDK 21 (newer JDKs fail with Gradle 8.14) with `JAVA_HOME` pointing at it, and the Android SDK in `ANDROID_HOME`. Android Studio installs the SDK. Run the checks before requesting a review. CI runs the same checks on every PR that changes `android/` or `web/`, and on every merge to `main`.

```sh
# From web/
npm run build
npx cap sync android

# From android/, with JAVA_HOME set to JDK 21
./gradlew coverageCheck    # Kotlin tests of both flavors, each with the 90% coverage gate
./gradlew checkFossHasNoGoogleServices   # foss holds no Google services (Flavors, below)
./gradlew assembleDebug    # Writes app/build/outputs/apk/<flavor>/debug/app-<flavor>-debug.apk for google and foss
```

Inner loop, without the coverage check, from `android/`: `./gradlew testGoogleDebugUnitTest --tests <test class>`. For code in `app/src/foss/`, use `testFossDebugUnitTest`.

Changed-file coverage, without the 90% gate, from `android/`: `./gradlew testGoogleDebugUnitTest --tests <test class> coverageReportGoogle`, then read the changed classes in `app/build/reports/jacoco/coverageReportGoogle/html/index.html` (`Foss` in both names for the `foss` flavor). Classes the named tests don't reach show as missed.

Run `npm run build` and `npx cap sync android` again after any web change, before building the app.

The coverage gate leaves out the Android glue that needs a phone; the list is `coverageExcludes` in `app/build.gradle`, and [docs/testing.md](../docs/testing.md#coverage-exclusions) says why each is excluded and which checklist covers it. New Android dependencies follow the same rules as npm ones: see [CODING_STANDARDS.md](../CODING_STANDARDS.md#dependencies).

Debug builds are **RollCall (dev)** (`io.github.sirmeili.rollcall.debug`, version `dev`), in both flavors. They install next to the release app instead of replacing it, each with its own pairing.

## Flavors

The app is built in two Gradle product flavors, released together:

- **`google`**: for phones with Google Play. It gets phone notifications through Google's push service (FCM) when the server has Firebase set up, with nothing else to install, and scans QR codes with Google's code scanner, which needs no camera permission.
- **`foss`**: contains no Google code, for phones without Google Play or people who avoid Google. It gets phone notifications only through a UnifiedPush distributor such as ntfy, and scans QR codes in the app with ZXing, asking for the camera the first time.

Pick `google` unless the phone has no Google Play or you'd rather avoid Google. `./gradlew checkFossHasNoGoogleServices` fails if `foss`'s dependencies hold Play services, Firebase, ML Kit or Google's data transport; CI and the release workflow run it. Open-source libraries that come from Google, such as ZXing or Gson, are allowed. See [ADR 0022](../docs/adr/0022-phone-notifications-through-official-fcm-or-unifiedpush-in-two-flavors.md) for why there are two flavors.

Both have the same app ID and are signed with the same key, so a phone switches by installing the other flavor's APK over the top: Android keeps the app's data, and the phone stays set up. A flavor's own code goes in `app/src/google/` or `app/src/foss/`, and its dependencies in `googleImplementation` or `fossImplementation`.

## Phone notifications

A user's phone (set up by signing in) shows the phone notifications its user chose on Account, even while the app is closed. A shared phone never gets them. They come through a [UnifiedPush](https://unifiedpush.org/) distributor, an app such as [ntfy](https://ntfy.sh/) installed on the phone, using the UnifiedPush connector library in both flavors, or, in `google` without a distributor, through Google's push service (FCM):

- **`google` with Firebase set up on the server** ([docs/deploy.md](../docs/deploy.md#firebase-optional)): nothing to install. The app gets Firebase's client settings from the server once signed in, and starts Firebase from them at app start, with no `google-services.json`, no Analytics, and automatic token creation and delivery-metrics export off. It sends its FCM token to the server as its endpoint. New Firebase settings, or pairing with another server, take effect after an app restart, which the app does by itself the next time it reads them. An installed distributor is still preferred over FCM.
- Otherwise, install ntfy (from F-Droid or Google Play). Without a distributor, and without FCM, the phone gets no phone notifications.
- Once signed in, the app registers with the distributor using the server's VAPID public key and sends its endpoint to the server with its session, from anywhere. A new endpoint from the distributor is sent at once, or on the next sign-in. With more than one distributor installed, it keeps the one in use, else the phone's default, else the first.
- ntfy uses the ntfy.sh server unless set to another; the server owner can run their own (see [docs/deploy.md](../docs/deploy.md#ntfy-optional)). The server encrypts each push for the phone (RFC 8291), so the ntfy server sees only encrypted contents.
- Each kind is its own Android notification channel, so a kind can also be muted in Android's settings. Tapping a notification opens its page, signing in first when signed out.

## Install a development build

- **USB:** turn on Developer options and USB debugging on the phone, connect it, then run `adb install -r app/build/outputs/apk/google/debug/app-google-debug.apk` (or the `foss` one). `adb` is in the SDK's `platform-tools`.
- **File:** copy `app-google-debug.apk` (or `app-foss-debug.apk`) to the phone and open it. Allow installs from that app when Android asks.

## Installing on a phone (releases, with Obtainium)

Everyday phones run the release app, **RollCall** (`io.github.sirmeili.rollcall`), from this repository's GitHub Releases. [Obtainium](https://github.com/ImranR98/Obtainium) watches the releases and offers each new version.

1. Install Obtainium from its [GitHub releases](https://github.com/ImranR98/Obtainium/releases) (the `app-release.apk` for most phones) or from F-Droid. Allow installs from the browser (or F-Droid) when Android asks.
2. In Obtainium, tap **Add app** and enter `https://github.com/sirmeili/rollcall`. Before adding, set:
   - **Filter release titles by regular expression:** `^RollCall app ` (the repository may hold other releases later).
   - **Version string extraction RegEx:** `(\d+\.\d+\.\d+)`, so the tag `app-v1.2.0` reads as `1.2.0`, the version the app reports.
   - **Filter APKs by regular expression**, for the flavor you picked (see [Flavors](#flavors)): `^rollcall-.*-google\.apk$` for `google`, or `^rollcall-.*-foss\.apk$` for `foss`.
3. Tap **Add**, then **Install**. Allow installs from Obtainium when Android asks.
4. Open RollCall **at home** and set it up by signing in (below). The server hands out the tag key and the Cloudflare Access token only on the home network.
5. Account shows the app's version (**RollCall app 1.2.0**); Devices shows each phone's version too.

Updates: Obtainium checks in the background and notifies when a release is out; tap **Update**. Android keeps the app's data, so the phone stays set up. An update must be signed with the same key as the installed app, so a phone with an app signed by another key (an old debug build) must uninstall it first.

A phone added in Obtainium before the flavors has the filter `^rollcall-.*\.apk$`, which matches both APKs: edit the app in Obtainium and set the filter for one flavor, as in step 2. To switch flavors later, change the filter and install: the phone stays set up.

## Releases

A release is published by pushing a tag `app-v<major>.<minor>.<patch>` (each part 0 to 99) on a commit in `main`. The **App release** workflow (`.github/workflows/app-release.yml`) then builds the web app and both flavors of the Android app at that version (version code `major·10000 + minor·100 + patch`), runs the Kotlin tests, signs them with the release key, checks each with `scripts/verify-release.sh` (app ID, version, a v2 signature and, when set, the expected certificate) and that both have the same certificate, and attaches `rollcall-<version>-google.apk` and `rollcall-<version>-foss.apk` to a GitHub Release named **RollCall app <version>**, with their SHA-256s, the certificate's SHA-256 and the merged pull requests.

```sh
git switch main && git pull
git tag app-v1.2.0
git push origin app-v1.2.0
```

A dry run (**Run workflow** on the Actions page, see step 5 below) does the same with any version and publishes nothing.

Make a release when a merged change affects the phone: the app holds its own copy of the web app, so a web change reaches the phones only in a new release. CI also builds a test release on every pull request that changes `android/` or `web/`, signed with a key made for that run, so a broken release setup shows up before a tag.

### The release key (once)

Every release must be signed with the same key: Android refuses an update signed by another, and the phones would have to uninstall and set up again. The owner keeps the key; it is never in the repository (`*.jks` is ignored).

1. Make it with JDK 21's `keytool`, in a folder outside the repository, choosing a long password when asked:

   ```sh
   keytool -genkeypair -keystore rollcall-release.jks -storetype PKCS12 -alias rollcall -keyalg RSA -keysize 4096 -validity 36500 -dname "CN=RollCall"
   ```

2. Keep the key and its password in a password manager, plus a second copy elsewhere (the `.jks` on a USB stick, say). Losing them means every phone reinstalls. A password manager that stores no files takes the key as text in a secure note (PowerShell, from the key's folder; `$PWD\` is needed because `[IO.File]` reads names from the folder PowerShell started in):

   ```powershell
   # Copy the key as text, to paste into the note
   [Convert]::ToBase64String([IO.File]::ReadAllBytes("$PWD\rollcall-release.jks")) | Set-Clipboard
   # Turn the note's text (copied) back into the file
   [IO.File]::WriteAllBytes("$PWD\rollcall-release.jks", [Convert]::FromBase64String((Get-Clipboard -Raw).Trim()))
   ```

   Check a restored copy with `keytool -list -keystore rollcall-release.jks -alias rollcall`: the same password and SHA-256 mean the backup is good.

3. Store them as repository secrets (PowerShell, from the key's folder):

   ```powershell
   [Convert]::ToBase64String([IO.File]::ReadAllBytes("$PWD\rollcall-release.jks")) | gh secret set ANDROID_KEYSTORE_BASE64 -R sirmeili/rollcall
   gh secret set ANDROID_KEYSTORE_PASSWORD -R sirmeili/rollcall   # paste the password when asked
   ```

4. Record the certificate's SHA-256, so the workflow refuses a release signed with any other key:

   ```powershell
   keytool -list -keystore rollcall-release.jks -alias rollcall   # asks for the password
   gh variable set RELEASE_CERT_SHA256 -R sirmeili/rollcall --body "<the SHA-256 without colons>"
   ```

5. Check the secrets with a dry run. GitHub never shows a secret again, so `gh secret list -R sirmeili/rollcall` only shows that they exist. On the Actions page, open **App release**, choose **Run workflow** on `main` and keep the version: it builds, signs and checks the app exactly as a release does, and publishes nothing. A green run, with the certificate's SHA-256 in its summary, means a tag will work. The secrets' values are never printed.

## Server for a phone test

The phone has to reach the server, so it must listen on the LAN, not only on `localhost`. From `server/`:

```sh
uv run uvicorn filament_tracker.main:create_app --factory --host 0.0.0.0 --port 8000
```

- Allow port 8000 through the PC's firewall for private networks.
- The pairing address is `http://<the PC's LAN address>:8000`. The app accepts plain `http://` only for LAN addresses.
- To sign in to the full web app over plain `http://`, also set `COOKIE_SECURE=false` in `server/.env`, for testing only. Scanning does not need it. Through the HTTPS reverse proxy, neither is needed.
- `BAMBU_KDF_SALT` must be set, or pairing stops with a message about it.

## Checklist

Run this before a release that changes the app, and record the results in the release's pull request.

**Setup and pairing**

1. First launch opens "Set up this phone", asking for the server's address, with "Pair with a code instead".
2. With NFC turned off in Android settings, Scan says NFC is off. Turn NFC on and come back: within a few seconds it asks for a tap, without restarting the app.
3. Pair with a code instead: on the PC, register a device on Devices, set the server address and show the QR code. Scan it in the app: the app opens Scan, and within a minute Devices shows the phone Online with version `app-1.0`.
4. Typed pairing: an `http://` address that is not on the LAN, such as `http://example.com`, is refused with a message about the home network.

**Scanning**

5. Tap a spool the server knows: once the whole tag is read the phone buzzes once and beeps (the beep follows the notification volume); the card then shows its name, color swatch and state with its date, and the suggested action is highlighted.
6. Choose an action: the app shows "Recorded …", and Activity shows the event from the phone.
7. Tap and choose nothing: after 15 seconds the screen goes back to waiting, and no event is recorded.
8. A known spool never offers the same action twice, so this one is checked offline (see 14).
9. Undo on the last scan: the app shows "Undid …", and Activity shows the event undone.
10. Tap a spool the server has never seen: New is offered, and choosing it adds the spool.
11. Tap a card that is not a Bambu tag, such as a transit card: nothing breaks, and the app keeps waiting for a tap.
12. Pull a spool away during the read: two short buzzes and a low tone, and the app keeps waiting for the next tap. Leave a spool on the phone after a read: it is not read again until it is lifted and tapped again.
13. A sealed spool reads through its box, as in M0a.

**Offline**

14. Stop the server, then tap a spool: the card shows the product decoded on the phone with New, Opened and Empty. Choose one: Scan shows "1 queued". Tap the same spool within 30 seconds and choose the same action: the app says it was already recorded, and the queue still holds one scan (check 8).
15. Undo the queued scan: the queue is empty, and nothing reaches the server later.
16. Queue another scan, then start the server: within a few minutes the queue empties, and Activity shows the event with the time of the tap.
17. Close the app fully and reopen it: it opens on Scan, still paired, and a queued scan is still queued.

**Full web app and unpairing**

18. Open the full app and sign in: pages work, and "Back to Scan" returns to Scan.
19. Revoke the phone's token on Devices: the next scan says to pair the phone again.
20. Unlink this phone (from Scan's Pairing button): it returns to Pairing, says the token was revoked, and Devices lists the phone as revoked.
21. Pair again, stop the server, then open the full app: "Cannot reach the server" offers Phone pairing. Unlink there: the app says the server could not be reached and the phone is still listed; Devices still shows it active until revoked there.
22. Away from home (mobile data, with the Access service token saved in Settings and the app opened once at home): the pages load without an Access sign-in, Scan shows Away, and a scan is decoded on the phone and queued. Back home, the queue empties and Activity shows the scan.
23. Without the service token, away from home: Scan shows Offline (not Online), a queued scan stays queued, and sign-in says it cannot reach the server instead of waiting.
24. With the phone on USB, `adb logcat` captured during pairing and a scan shows no device token, tag key constant, tag UID or block data. Search it for `ftd_` and for the UID's hex digits.

**Setting up by signing in**

25. Unlink, then at home enter the server's address and sign in as an Editor: the app sets itself up without a code and asks what the phone is mainly for. Devices lists the phone under its model name, belonging to that user.
26. Choose "Looking at stock": the app opens on Inventory, now and after closing and reopening it. Change it to "Scanning" on the Pairing page: it opens on Scan.
27. Scan a spool and record an action: Activity shows it as "user (phone model)".
28. Set up a phone as a Viewer: tapping a spool shows its card with Info and Cancel only and "Your account can look spools up but not record them", online and with the server stopped.
29. Try setting up away from home (mobile data): the app says to finish setting up at home. "Use a different server" goes back to the address.
30. Unlink a phone set up by signing in: it is signed out and back at the address step.

**Back button**

Run each step with the swipe-back gesture and, where the phone has one, the Back key.

31. Back a page: from Inventory open a spool, then hop to Activity with the bottom nav. Back returns to the spool, and Back again to Inventory.
32. The opening screen to the background: close the app fully and reopen it, so Scan has nothing before it. Turn on Delivery and record a spool, then press Back: the app goes to the background without closing. Reopen it from the recent apps: Scan shows, with Delivery on and the spool in its list.
33. Nothing on the start screen: close the app fully, reopen it and press Back while the start screen shows. Nothing happens, and the app opens as usual.
34. The menu sheet closes first: on Inventory open the menu, then press Back. The menu closes and Inventory stays. Open the filter sheet, then the menu over it: Back closes the menu only, and Back again the filter sheet.
35. A filter sheet closes first: on Spools open the filter sheet and choose a state, then press Back. The sheet closes, Spools stays, and the filters are as they were. Do the same on Catalog.
36. A dialog closes first: as an Admin, open a submitted print request, tap Reject, then press Back. The dialog closes, the request stays Submitted, and Back again leaves the page.
37. A scan card before choosing an action: on Scan tap a spool, then press Back. The card closes, Scan is back at Ready, and nothing is recorded: Activity has no new event. Do the same with Delivery on: Delivery stays on and its list is unchanged.
38. A scan card after choosing an action: on Scan tap a spool and choose an action, then press Back. The card closes and Scan is back at Ready, with the action kept, not undone: Activity shows it. Do the same with Delivery on: Delivery stays on and the spool stays in its list.
39. After pairing (QR code, typed code, or setting up by signing in), Back from the opened page sends the app to the background.
40. After saving a form (a new print request, an edited request, a new spool), Back from the page it opens skips the form.
41. The leave warning: start a new print request and type a title, then press Back. "Leave without saving?" shows: Back on it, or Stay, keeps the form with the title. Press Back again and choose Leave: the previous page shows. Open a submitted request as an Admin, tap Reject, type a reason and press Back: the warning shows, Stay keeps the dialog and the reason, and Leave closes it.

**Flavors**

42. On a phone set up with the `google` release, install the `foss` APK of the same or a newer version over the top: it installs without uninstalling, opens still set up (Scan, or the page chosen in 26) and a scan records. Install the `google` APK back over it: still set up.

**Phone notifications**

43. On a phone set up by signing in, with ntfy installed and RollCall's notifications allowed in Android's settings, close the app and turn Wi-Fi off (mobile data). From a PC, mark one of that user's print requests Done: the notification shows within a minute, and Android's settings for RollCall list a channel for each kind.
44. Tap it: the app opens on the request's page.
45. Sign out in the full app, then tap a new notification: the app asks to sign in, then opens its page.
46. On a shared phone (paired with a code) with ntfy installed, sign in to the full app: ntfy lists no RollCall subscription, and no notifications arrive.
47. `google` via FCM: with Firebase set up on the Settings page, on a `google` phone without ntfy (or any other distributor), sign in: the app restarts itself once, then its phone settings say phone notifications work via Google. Close the app, turn Wi-Fi off and mark one of the user's requests Done from a PC: the notification shows, and tapping it opens the request.
48. `google` with ntfy installed uses ntfy: install ntfy on the phone from 47 and open RollCall: ntfy lists a RollCall subscription, the phone settings say via ntfy, and the next notification arrives through ntfy.
49. `foss` via ntfy: on a `foss` phone with ntfy, steps 43 and 44 pass, and Firebase set up on the server changes nothing (no restart).
50. Change a Firebase setting on the Settings page (or pair the `google` phone with another server): the next time the app opens signed in it restarts itself once, and FCM notifications still arrive.
51. `foss` QR code: on a `foss` phone, Pair with a code instead and scan the Devices page's QR code: the app asks for the camera the first time, the ZXing scanner reads the code held upright, and pairing finishes as in 3. Back out of the scanner: the app returns to Pairing with nothing scanned.

A phone without MIFARE Classic support should say so on Scan. A Pixel cannot show this, so it is covered by the web tests only.
