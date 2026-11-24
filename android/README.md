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
- Done and New photo show the print's first photo as a large picture. The app downloads it from the paired server with its signed-in session and the Cloudflare Access service token, as its other calls do; signed out, or if the download fails, the notification shows its text only.
- Android 13 and later ask once for permission to show notifications: after setting the phone up by signing in, or on the first open of a phone set up before phone notifications came. Refusing it changes no setting on Account.
- Pairing's **Phone notifications** line says whether they work on this phone and by which route ("via Google" or "via ntfy"), that RollCall isn't allowed to show notifications and how to allow it, or that the phone has no distributor and ntfy should be installed. **Send a test notification** asks the server to send one to this phone.
- Unlink and sign-out first unregister from the route (the distributor, or deleting the FCM token), so the phone stops getting them even away from home, then remove its endpoint on the server if it answers, then sign out or forget the pairing.

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

Obtainium skips release candidates, which are prereleases, so an everyday phone only gets final releases. A **test phone** also takes release candidates: edit RollCall in Obtainium, turn on **Include prereleases** and set the version RegEx to `(\d+\.\d+\.\d+(?:-rc\.\d+)?)`. Each release candidate, and then the final release, installs over the top and the phone stays set up ([docs/releasing.md, Installing a release candidate](../docs/releasing.md#installing-a-release-candidate)).

A phone added in Obtainium before the flavors has the filter `^rollcall-.*\.apk$`, which matches both APKs: edit the app in Obtainium and set the filter for one flavor, as in step 2. To switch flavors later, change the filter and install: the phone stays set up.

## Releases

[docs/releasing.md](../docs/releasing.md) is the release procedure: versions, the publish commands, the checks after each, and the release record. In short, every release goes through at least one release candidate, a tag such as `app-v1.3.0-rc.1` on a commit in `main`, published as a GitHub prerelease for test phones. The final release is the tag `app-v1.3.0` on the newest release candidate's commit, and the workflow refuses it until the release record, the open issue `App release 1.3.0`, carries the `release-approved` label.

For either tag, the **App release** workflow (`.github/workflows/app-release.yml`) builds the web app and both flavors of the Android app at that version (version code `major·10000 + minor·100 + patch`, shared by a release candidate and its final release), runs the Kotlin tests, signs them with the release key, checks each with `scripts/verify-release.sh` (app ID, version, a v2 signature and, when set, the expected certificate) and that both have the same certificate, and attaches `rollcall-<version>-google.apk` and `rollcall-<version>-foss.apk` to a GitHub Release named **RollCall app <version>**, with their SHA-256s, the certificate's SHA-256 and the pull requests merged since the last final release.

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

Run on each release candidate, on the release-signed APK installed from it. [docs/releasing.md](../docs/releasing.md#checklist) says how a release is scoped and run, and where the results go: the release's record issue.

- **Step ids.** A step's number is its id, and it never changes: a new step is added at the end, and a removed step stays as `Retired.`, so a `Result:` line and a reference such as "as in 3" keep meaning the same step.
- **Flavors.** Each step names the flavor it needs: `[either]` runs once, on either flavor; `[both]` runs on `google` and on `foss`; `[google]` and `[foss]` run on that flavor only.
- **Always**, on every release candidate, whatever changed: 3, 5, 6, 14, 16, 18, 25, 42, 48, 49.
- **Triggers.** Each section names the app's Kotlin code and the web app's code that trigger it. Paths are under `android/app/src/` and `web/src/`, and a class's name covers its file in any source set (`main`, `google`, `foss`). A changed file runs every section that names it.
- **Shared web code** runs Full web app and unpairing, and Back button: the API client and its errors (`lib/api/client.ts`, `lib/api/errors.ts`), the shared components (`lib/components/*.svelte`, `lib/components/shell/`, `lib/components/ui/`), the root layout (`routes/+layout.svelte`, `routes/+layout.ts`), the global styles and theme (`app.css`, `lib/theme.svelte.ts`, `lib/fonts.ts`, `lib/viewport.svelte.ts`), the HTML shell (`app.html`), and the web app's build and dependencies (`web/package.json`, `web/package-lock.json`, `web/vite.config.ts`, `web/tsconfig.json`).
- **Unmapped files.** A changed file in `android/` or `web/` (or a part of `android/app/build.gradle`) that no section names makes the release a full run, and the record lists it, so its section can be named here. Files that aren't built into the app trigger nothing: tests (`*.test.ts`, `web/src/test/`, `web/e2e/`, `android/app/src/test*/`), docs (`*.md`), and the checks in `android/scripts/` and `web/scripts/`.
- **Full run**, the whole checklist: a major or minor version; a changed release key; a Capacitor, Gradle, Android Gradle Plugin, Kotlin or Android SDK upgrade; a `targetSdk` or `minSdk` change; or a change to the permissions in an `AndroidManifest.xml`.

**Setup and pairing**

*Triggers.* Kotlin: `MainActivity`, `FilamentTrackerPlugin`, `SecureStore`, `NfcState`, `Flavor` (its QR scanner). Web: the Pair route (`routes/pair/`), the phone's set-up and pairing screens (`lib/components/phone/` `SetUpPhone`, `ServerAddress`, `PairWithCode`, `PairedPhone`, `StartScreen`, and `lib/start-screen.ts`), pairing (`lib/pairing.ts`, `lib/phone/pairing-store.ts`), the phone bridge (`lib/phone/bridge.ts`, `lib/phone/native-bridge.ts`), the phone's session and state (`lib/phone/session.ts`, `lib/phone/phone-state.svelte.ts`), the device API (`lib/phone/device-api.ts`), and the Devices route (`routes/devices/`, `lib/components/devices/`, `lib/devices.ts`).

1. `[either]` First launch opens "Set up this phone", asking for the server's address, with "Pair with a code instead".
2. `[either]` With NFC turned off in Android settings, Scan says NFC is off. Turn NFC on and come back: within a few seconds it asks for a tap, without restarting the app.
3. `[either]` Pair with a code instead: on the PC, register a device on Devices, set the server address and show the QR code. Scan it in the app: the app opens Scan, and within a minute Devices shows the phone Online with the release candidate's version, such as `app-1.3.0-rc.1`, and Account shows **RollCall app 1.3.0-rc.1**.
4. `[either]` Typed pairing: an `http://` address that is not on the LAN, such as `http://example.com`, is refused with a message about the home network.

**Scanning**

*Triggers.* Kotlin: `TagReader`, `AndroidMifare`, `TagKeys`, `Hex`, `FilamentTrackerPlugin`. Web: the Scan route (`routes/scan/`), the scan flow (`lib/phone/scan-flow.ts`, `lib/phone/pause.ts`, `lib/phone/card-text.ts`), decoding a tag on the phone (`lib/phone/tag-decode.ts`), Delivery (`lib/phone/delivery.svelte.ts`), the scan screen's components (`lib/components/phone/` `ActionKeys`, `CardChip`, `CountdownBar`, `DeliveryList`, `DeliveryPanel`, `DeliveryToggle`, `LastScanBar`, `ScanCard`, `ScanHeader`, `ScanIcon`, `ScanResult`, `TapTarget`), and the phone bridge (`lib/phone/bridge.ts`, `lib/phone/native-bridge.ts`).

5. `[either]` Tap a spool the server knows: once the whole tag is read the phone buzzes once and beeps (the beep follows the notification volume); the card then shows its name, color swatch and state with its date, and the suggested action is highlighted.
6. `[either]` Choose an action: the app shows "Recorded …", and Activity shows the event from the phone.
7. `[either]` Tap and choose nothing: after 15 seconds the screen goes back to waiting, and no event is recorded.
8. `[either]` A known spool never offers the same action twice, so this one is checked offline (see 14).
9. `[either]` Undo on the last scan: the app shows "Undid …", and Activity shows the event undone.
10. `[either]` Tap a spool the server has never seen: New is offered, and choosing it adds the spool.
11. `[either]` Tap a card that is not a Bambu tag, such as a transit card: nothing breaks, and the app keeps waiting for a tap.
12. `[either]` Pull a spool away during the read: two short buzzes and a low tone, and the app keeps waiting for the next tap. Leave a spool on the phone after a read: it is not read again until it is lifted and tapped again.
13. `[either]` A sealed spool reads through its box, as in M0a.

**Offline**

*Triggers.* Kotlin: `AndroidStorage`. Web: the offline queue (`lib/phone/queue.ts`), decoding a tag on the phone (`lib/phone/tag-decode.ts`), and the phone's session and state (`lib/phone/session.ts`, `lib/phone/phone-state.svelte.ts`, `lib/phone/device-api.ts`), which say whether it is Online, Away or Offline.

14. `[either]` Stop the server, then tap a spool: the card shows the product decoded on the phone with New, Opened and Empty. Choose one: Scan shows "1 queued". Tap the same spool within 30 seconds and choose the same action: the app says it was already recorded, and the queue still holds one scan (check 8).
15. `[either]` Undo the queued scan: the queue is empty, and nothing reaches the server later.
16. `[either]` Queue another scan, then start the server: within a few minutes the queue empties, and Activity shows the event with the time of the tap.
17. `[either]` Close the app fully and reopen it: it opens on Scan, still paired, and a queued scan is still queued.

**Full web app and unpairing**

*Triggers.* Kotlin: none. Web: shared web code (above), sign-in and the session (`lib/auth/`, `routes/login/`, `lib/components/LoginForm.svelte`), the Devices route (`routes/devices/`, `lib/components/devices/`, `lib/devices.ts`), unlinking (`lib/components/phone/PairedPhone.svelte`, `routes/pair/`), and every page of the full web app that no other section names: its route under `routes/`, its components under `lib/components/`, and its `lib/` and `lib/api/` modules.

18. `[either]` Open the full app and sign in: pages work, and "Back to Scan" returns to Scan.
19. `[either]` Revoke the phone's token on Devices: the next scan says to pair the phone again.
20. `[either]` Unlink this phone (from Scan's Pairing button): it returns to Pairing, says the token was revoked, and Devices lists the phone as revoked.
21. `[either]` Pair again, stop the server, then open the full app: "Cannot reach the server" offers Phone pairing. Unlink there: the app says the server could not be reached and the phone is still listed; Devices still shows it active until revoked there.
22. `[either]` Away from home (mobile data, with the Access service token saved in Settings and the app opened once at home): the pages load without an Access sign-in, Scan shows Away, and a scan is decoded on the phone and queued. Back home, the queue empties and Activity shows the scan.
23. `[either]` Without the service token, away from home: Scan shows Offline (not Online), a queued scan stays queued, and sign-in says it cannot reach the server instead of waiting.
24. `[either]` With the phone on USB, `adb logcat` captured during pairing and a scan shows no device token, tag key constant, tag UID or block data. Search it for `ftd_` and for the UID's hex digits.

**Setting up by signing in**

*Triggers.* Kotlin: `SecureStore`. Web: the Login route (`routes/login/`, `lib/components/LoginForm.svelte`), setting the phone up as a user's own (`lib/phone/own-phone.ts`), the address step (`lib/components/phone/SetUpPhone.svelte`, `ServerAddress.svelte`), the screen it opens on (`lib/components/phone/OpensOn.svelte`), the start screen (`lib/components/phone/StartScreen.svelte`, `lib/start-screen.ts`), and roles (`lib/roles.ts`).

25. `[either]` Unlink, then at home enter the server's address and sign in as an Editor: the app sets itself up without a code and asks what the phone is mainly for. Devices lists the phone under its model name, belonging to that user.
26. `[either]` Choose "Looking at stock": the app opens on Inventory, now and after closing and reopening it. Change it to "Scanning" on the Pairing page: it opens on Scan.
27. `[either]` Scan a spool and record an action: Activity shows it as "user (phone model)".
28. `[either]` Set up a phone as a Viewer: tapping a spool shows its card with Info and Cancel only and "Your account can look spools up but not record them", online and with the server stopped.
29. `[either]` Try setting up away from home (mobile data): the app says to finish setting up at home. "Use a different server" goes back to the address.
30. `[either]` Unlink a phone set up by signing in: it is signed out and back at the address step.

**Back button**

*Triggers.* Kotlin: `MainActivity` (Back itself is Capacitor's App plugin, so its upgrade is a full run). Web: shared web code (above), Back handling (`lib/phone/back.ts`, `lib/phone/back-layer.svelte.ts`, `lib/phone/bridge.ts`, `lib/phone/native-bridge.ts`), navigation (`lib/nav.ts`), the leave warning (`lib/leave-warning.svelte.ts`, `lib/components/LeaveWarning.svelte`), the focus trap (`lib/focus-trap.ts`), the start screen (`lib/components/phone/StartScreen.svelte`), Delivery and the scan card (`lib/phone/delivery.svelte.ts`, `lib/components/phone/ScanCard.svelte`), and every sheet and dialog: any `*Sheet.svelte` or `*Dialog.svelte` under `lib/components/` (the menu sheet, the filter sheets, the print request and catalog color dialogs).

Run each step with the swipe-back gesture and, where the phone has one, the Back key.

31. `[either]` Back a page: from Inventory open a spool, then hop to Activity with the bottom nav. Back returns to the spool, and Back again to Inventory.
32. `[either]` The opening screen to the background: close the app fully and reopen it, so Scan has nothing before it. Turn on Delivery and record a spool, then press Back: the app goes to the background without closing. Reopen it from the recent apps: Scan shows, with Delivery on and the spool in its list.
33. `[either]` Nothing on the start screen: close the app fully, reopen it and press Back while the start screen shows. Nothing happens, and the app opens as usual.
34. `[either]` The menu sheet closes first: on Inventory open the menu, then press Back. The menu closes and Inventory stays. Open the filter sheet, then the menu over it: Back closes the menu only, and Back again the filter sheet.
35. `[either]` A filter sheet closes first: on Spools open the filter sheet and choose a state, then press Back. The sheet closes, Spools stays, and the filters are as they were. Do the same on Catalog.
36. `[either]` A dialog closes first: as an Admin, open a submitted print request, tap Reject, then press Back. The dialog closes, the request stays Submitted, and Back again leaves the page.
37. `[either]` A scan card before choosing an action: on Scan tap a spool, then press Back. The card closes, Scan is back at Ready, and nothing is recorded: Activity has no new event. Do the same with Delivery on: Delivery stays on and its list is unchanged.
38. `[either]` A scan card after choosing an action: on Scan tap a spool and choose an action, then press Back. The card closes and Scan is back at Ready, with the action kept, not undone: Activity shows it. Do the same with Delivery on: Delivery stays on and the spool stays in its list.
39. `[either]` After pairing (QR code, typed code, or setting up by signing in), Back from the opened page sends the app to the background.
40. `[either]` After saving a form (a new print request, an edited request, a new spool), Back from the page it opens skips the form.
41. `[either]` The leave warning: start a new print request and type a title, then press Back. "Leave without saving?" shows: Back on it, or Stay, keeps the form with the title. Press Back again and choose Leave: the previous page shows. Open a submitted request as an Admin, tap Reject, type a reason and press Back: the warning shows, Stay keeps the dialog and the reason, and Leave closes it.

**Flavors**

*Triggers.* Kotlin: `AppFlavor`, `Flavor`, and the Gradle flavors: `productFlavors`, the `googleImplementation` and `fossImplementation` dependencies and `checkFossHasNoGoogleServices` in `android/app/build.gradle`, and the `google` and `foss` `AndroidManifest.xml`. Web: none.

42. `[both]` On a phone set up with one flavor of this release candidate, install the other flavor's APK of the same release candidate over the top: it installs without uninstalling, opens still set up (Scan, or the page chosen in 26) and a scan records. Install the first flavor's APK back over it: still set up. Start once from each flavor.

**Phone notifications**

*Triggers.* Kotlin: `PushBridge`, `PushRoutes`, `PushEndpointStore`, `PushEvents`, `Notifier`, `PhoneNotification`, `NotificationChannels`, `Distributors`, `UnifiedPush*`, `Firebase*`, `FcmRoute`, `GoogleRoutes`, `Photo*`, `Flavor` (its push routes), `FilamentTrackerPlugin`. Web: the phone's notifications (`lib/phone/push.ts`, `lib/phone/permission.ts`, `lib/phone/notification-status.ts`, `lib/components/phone/PhoneNotifications.svelte`), the Account route and its Notifications list (`routes/account/`, `lib/components/account/NotificationSettings.svelte`, `lib/notifications.ts`), and the Firebase settings (`lib/components/settings/PhoneNotificationSettings.svelte`). Also the server's push sender (`server/src/filament_tracker/push/`, `server/src/filament_tracker/api/push.py`) when it changed since the last release, though it ships in the server image, not the app.

43. `[either]` On a phone set up by signing in, with ntfy installed and RollCall's notifications allowed in Android's settings, close the app and turn Wi-Fi off (mobile data). From a PC, mark one of that user's print requests Done: the notification shows within a minute, and Android's settings for RollCall list a channel for each kind.
44. `[either]` Tap it: the app opens on the request's page.
45. `[either]` Sign out in the full app, then tap a new notification: the app asks to sign in, then opens its page.
46. `[either]` On a shared phone (paired with a code) with ntfy installed, sign in to the full app: ntfy lists no RollCall subscription, and no notifications arrive.
47. `[either]` On an Android 13 or later phone, set it up by signing in: Android asks once whether RollCall may show notifications. Refuse: Pairing says RollCall isn't allowed to show notifications and how to allow it, and Account's Phone switches are unchanged. Allow notifications in Android's settings and come back: Pairing says they work, via ntfy. Close and reopen the app: it doesn't ask again.
48. `[both]` On a phone set up by signing in with the previous release of the same flavor, install this release candidate from Obtainium ([docs/releasing.md](../docs/releasing.md#installing-a-release-candidate)): it installs as an update, without uninstalling, and opens still set up, on the page chosen in 26, and a scan records. On the first open (at home), Android asks once whether RollCall may show notifications when the previous release had no phone notifications (1.2.0 and older), and doesn't ask when it had; reopening never asks again.
49. `[either]` On Pairing, tap Send a test notification: "Sent a test notification to this phone" shows, and the notification arrives. Uninstall ntfy and open Pairing: it says to install ntfy.
50. `[either]` Away from home (mobile data), unlink the phone: ntfy no longer lists a RollCall subscription, and marking one of that user's print requests Done from a PC shows no notification on it.
51. `[either]` On Wi-Fi at home, with the app closed, mark one of that user's print requests Done with a photo from a PC: the notification shows the photo, and expanding it shows it large. Do it again away from home (mobile data), with Cloudflare Access in front of the server: the photo shows too. Sign out in the full app and do it once more: the notification shows its text only.
52. `[google]` `google` via FCM: set up Firebase on the Settings page, choosing the downloaded service-account key file in a desktop browser, then once more in the full app on a phone: each time the field shows the file's name and the service account's email, and Save says Saved. On a `google` phone without ntfy (or any other distributor), sign in: the app restarts itself once, then Pairing says phone notifications work via Google. Tap Send a test notification: it arrives. Close the app, turn Wi-Fi off and mark one of the user's requests Done with a photo from a PC: the notification shows with the photo, and tapping it opens the request.
53. `[google]` `google` with ntfy installed uses ntfy: install ntfy on the phone from 52 and open RollCall: ntfy lists a RollCall subscription, Pairing says via ntfy, and the next notification arrives through ntfy.
54. `[foss]` `foss` via ntfy: on a `foss` phone with ntfy, steps 43 and 44 pass, and Firebase set up on the server changes nothing (no restart).
55. `[google]` Change a Firebase setting on the Settings page (or pair the `google` phone with another server): the next time the app opens signed in it restarts itself once, and FCM notifications still arrive.
56. `[foss]` `foss` QR code: on a `foss` phone, Pair with a code instead and scan the Devices page's QR code: the app asks for the camera the first time, the ZXing scanner reads the code held upright, and pairing finishes as in 3. Back out of the scanner: the app returns to Pairing with nothing scanned.

A phone without MIFARE Classic support should say so on Scan. A Pixel cannot show this, so it is covered by the web tests only.
