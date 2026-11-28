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
   - **Version string extraction RegEx:** `(\d+\.\d+\.\d+)`, so the tag `v1.4.0` reads as `1.4.0`, the version the app reports (and the older `app-v1.3.0` as `1.3.0`).
   - **Filter APKs by regular expression**, for the flavor you picked (see [Flavors](#flavors)): `^rollcall-.*-google\.apk$` for `google`, or `^rollcall-.*-foss\.apk$` for `foss`.
3. Tap **Add**, then **Install**. Allow installs from Obtainium when Android asks.
4. Open RollCall **at home** and set it up by signing in (below). The server hands out the tag key and the Cloudflare Access token only on the home network.
5. Account shows the app's version (**RollCall app 1.4.0**); Devices shows each phone's version too.

Updates: Obtainium checks in the background and notifies when a release is out; tap **Update**. Android keeps the app's data, so the phone stays set up. An update must be signed with the same key as the installed app, so a phone with an app signed by another key (an old debug build) must uninstall it first.

Obtainium skips release candidates, which are prereleases, so an everyday phone only gets final releases. A **test phone** also takes release candidates: edit RollCall in Obtainium, turn on **Include prereleases** and set the version RegEx to `(\d+\.\d+\.\d+(?:-rc\.\d+)?)`. Each release candidate, and then the final release, installs over the top and the phone stays set up ([docs/releasing.md, Installing a release candidate](../docs/releasing.md#installing-a-release-candidate)).

A phone added in Obtainium before the flavors has the filter `^rollcall-.*\.apk$`, which matches both APKs: edit the app in Obtainium and set the filter for one flavor, as in step 2. To switch flavors later, change the filter and install: the phone stays set up.

## Releases

The app is released together with the server, as one release of RollCall at one version ([ADR-0025](../docs/adr/0025-one-release-for-the-app-and-the-server.md)). [docs/releasing.md](../docs/releasing.md) is the release procedure: versions, the publish commands, the checks after each, the test server and the release record. In short, every release goes through at least one release candidate, a tag such as `v1.4.0-rc.1` on a commit in `main`, published as a GitHub prerelease for test phones and tested on a test server. The final release is the tag `v1.4.0` on the newest release candidate's commit, and the workflow refuses it until the release record, the open issue `RollCall release 1.4.0`, carries the `release-approved` label. Releases up to 1.3.0 were the app alone, tagged `app-v<version>`.

For either tag, the **Release** workflow (`.github/workflows/release.yml`) builds the web app and both flavors of the Android app at that version (version code `major·1000000 + minor·1000 + patch`, shared by a release candidate and its final release), runs the Kotlin tests, signs them with the release key, checks each with `scripts/verify-release.sh` (app ID, version, a v2 signature and, when set, the expected certificate) and that both have the same certificate, and attaches `rollcall-<version>-google.apk` and `rollcall-<version>-foss.apk` to a GitHub Release named **RollCall app and server <version>**, with their SHA-256s, the certificate's SHA-256, the server image's tags and digest, and the pull requests merged since the previous final release. It builds, tests and publishes the server image in the same run (docs/releasing.md). The title keeps starting with `RollCall app `, which everyday phones' Obtainium filter needs.

A dry run (**Run workflow** on the Actions page, see step 5 below) does the same with a version you give, such as `1.2.3` or `1.2.3-rc.1`, image included, and publishes nothing. It refuses a malformed version ([docs/releasing.md, Versioning](../docs/releasing.md#versioning)), but skips the release candidate and record rules.

Make a release when a merged change affects the phone or the server: the app holds its own copy of the web app, so a web change reaches the phones only in a new release, and everyday servers run only final releases. CI also builds a test release on every pull request that changes `android/` or `web/`, signed with a key made for that run, so a broken release setup shows up before a tag.

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

5. Check the secrets with a dry run. GitHub never shows a secret again, so `gh secret list -R sirmeili/rollcall` only shows that they exist. On the Actions page, open **Release**, choose **Run workflow** on `main` and keep the version: it builds, signs and checks the app exactly as a release does, tests the image too, and publishes nothing. A green run, with the certificate's SHA-256 in its summary, means a tag will work. The secrets' values are never printed.

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

The release checklist, run on each release candidate, is in [docs/checklist.md](../docs/checklist.md).
