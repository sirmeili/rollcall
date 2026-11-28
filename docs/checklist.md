# Release checklist

Run on each release candidate: the phone steps on the release-signed APK installed from it, on a test phone paired with the test server, and the browser steps in a desktop browser on the test server, once it runs the candidate. [docs/releasing.md](releasing.md#checklist) says how a release is scoped and run, and where the results go: the release's record issue.

- **Step ids.** A step's number is its id, and it never changes: a new step is added at the end, and a removed step stays as `Retired.`, so a `Result:` line and a reference such as "as in 3" keep meaning the same step.
- **Flavors.** Each step names the flavor it needs: `[either]` runs once, on either flavor; `[both]` runs on `google` and on `foss`; `[google]` and `[foss]` run on that flavor only. `[browser]` runs once, in a desktop browser.
- **The server** in every step is the test server ([GLOSSARY.md](../GLOSSARY.md), Test server), never the live one: its address, stopping and starting it, and pairing with it all mean the test server. It is restored on the previous release and upgraded to the candidate before the checklist starts ([docs/releasing.md](releasing.md)).
- **Always**, on every release candidate, whatever changed: 3, 5, 6, 14, 16, 18, 25, 42, 48, 49, 62.
- **Triggers.** Each section names the app's Kotlin code, the web app's code and the server's files that trigger it. Kotlin and web paths are under `android/app/src/` and `web/src/`, server paths under `server/src/filament_tracker/` unless they start at the repository's root, and a class's name covers its file in any source set (`main`, `google`, `foss`). A changed file runs every section that names it.
- **Shared web code** runs Full web app and unpairing, Back button, and Web app: the API client and its errors (`lib/api/client.ts`, `lib/api/errors.ts`), the shared components (`lib/components/*.svelte`, `lib/components/shell/`, `lib/components/ui/`), the root layout (`routes/+layout.svelte`, `routes/+layout.ts`), the global styles and theme (`app.css`, `lib/theme.svelte.ts`, `lib/fonts.ts`, `lib/viewport.svelte.ts`), the HTML shell (`app.html`), and the web app's build and dependencies (`web/package.json`, `web/package-lock.json`, `web/vite.config.ts`, `web/tsconfig.json`).
- **Unmapped files.** A changed non-test file in the app, web or server source (or a part of `android/app/build.gradle`), or a file under `server/` or `deploy/`, that no section names makes the release a full run, and the record lists it, so its section can be named here. Test files trigger nothing (`*.test.ts`, `web/src/test/`, `web/e2e/`, `android/app/src/test*/`, `server/tests/`, the end-to-end stack `deploy/test/`, and the fake printer's broker `server/fakeprinter/`). Nor do files in `android/`, `web/` or `server/` that are not app, web or server source: docs (`*.md`), and the checks in `android/scripts/` and `web/scripts/`, which aren't built into the app.
- **Full run**, the whole checklist: a major or minor version; a changed release key; a Capacitor, Gradle, Android Gradle Plugin, Kotlin or Android SDK upgrade; a `targetSdk` or `minSdk` change; a change to the permissions in an `AndroidManifest.xml`; a change to the image's base (the `python` image in `Dockerfile`'s `FROM` lines, other than a digest update) or to the server's Python version (`requires-python` in `server/pyproject.toml`); or a migration that restoring a backup can't undo, such as one that changes files outside the database.

**Setup and pairing**

*Triggers.* Kotlin: `MainActivity`, `FilamentTrackerPlugin`, `SecureStore`, `NfcState`, `Flavor` (its QR scanner). Web: the Pair route (`routes/pair/`), the phone's set-up and pairing screens (`lib/components/phone/` `SetUpPhone`, `ServerAddress`, `PairWithCode`, `PairedPhone`, `StartScreen`, and `lib/start-screen.ts`), pairing (`lib/pairing.ts`, `lib/phone/pairing-store.ts`), the phone bridge (`lib/phone/bridge.ts`, `lib/phone/native-bridge.ts`), the phone's session and state (`lib/phone/session.ts`, `lib/phone/phone-state.svelte.ts`), the device API (`lib/phone/device-api.ts`), and the Devices route (`routes/devices/`, `lib/components/devices/`, `lib/devices.ts`).

1. `[either]` First launch opens "Set up this phone", asking for the server's address, with "Pair with a code instead".
2. `[either]` With NFC turned off in Android settings, Scan says NFC is off. Turn NFC on and come back: within a few seconds it asks for a tap, without restarting the app.
3. `[either]` Pair with a code instead: on the PC, register a device on Devices, set the test server's address and show the QR code. Scan it in the app: the app opens Scan, and within a minute Devices shows the phone Online with the release candidate's version, such as `app-1.3.0-rc.1`, and Account shows **RollCall app 1.3.0-rc.1**.
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

*Triggers.* Kotlin: none. Web: shared web code (above), sign-in and the session (`lib/auth/`, `routes/login/`, `lib/components/LoginForm.svelte`), the Devices route (`routes/devices/`, `lib/components/devices/`, `lib/devices.ts`), and unlinking (`lib/components/phone/PairedPhone.svelte`, `routes/pair/`). A page of the full web app that no section names is an unmapped file (above), so it makes a full run.

18. `[either]` Open the full app and sign in: pages work, and "Back to Scan" returns to Scan.
19. `[either]` Revoke the phone's token on Devices: the next scan says to pair the phone again.
20. `[either]` Unlink this phone (from Scan's Pairing button): it returns to Pairing, says the token was revoked, and Devices lists the phone as revoked.
21. `[either]` Pair again, stop the server, then open the full app: "Cannot reach the server" offers Phone pairing. Unlink there: the app says the server could not be reached and the phone is still listed; Devices still shows it active until revoked there.
22. `[either]` Away from home (mobile data, with the Access service token saved in Settings and the app opened once at home): the pages load without an Access sign-in, Scan shows Away, and a scan is decoded on the phone and queued. Back home, the queue empties and Activity shows the scan.
23. `[either]` Without the service token, away from home: Scan shows Offline (not Online), a queued scan stays queued, and sign-in says it cannot reach the server instead of waiting.
24. `[either]` With the phone on USB, `adb logcat` captured during pairing and a scan shows no device token, tag key constant, tag UID or block data. Search it for `ftd_` and for the UID's hex digits.

**Setting up by signing in**

*Triggers.* Kotlin: `SecureStore`. Web: the Login route (`routes/login/`, `lib/components/LoginForm.svelte`), setting the phone up as a user's own (`lib/phone/own-phone.ts`), the address step (`lib/components/phone/SetUpPhone.svelte`, `ServerAddress.svelte`), the screen it opens on (`lib/components/phone/OpensOn.svelte`), the start screen (`lib/components/phone/StartScreen.svelte`, `lib/start-screen.ts`), and roles (`lib/roles.ts`).

25. `[either]` Unlink, then at home enter the test server's address and sign in as an Editor: the app sets itself up without a code and asks what the phone is mainly for. Devices lists the phone under its model name, belonging to that user.
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
48. `[both]` On a test phone with the previous release of the same flavor, set up by signing in to the test server while it still ran the previous release, install this release candidate from Obtainium once the test server is upgraded to it ([docs/releasing.md](releasing.md#installing-a-release-candidate)): it installs as an update, without uninstalling, and opens still set up with the test server, on the page chosen in 26, and a scan records. On the first open (at home), Android asks once whether RollCall may show notifications when the previous release had no phone notifications (1.2.0 and older), and doesn't ask when it had; reopening never asks again.
49. `[either]` On Pairing, tap Send a test notification: "Sent a test notification to this phone" shows, and the notification arrives. Uninstall ntfy and open Pairing: it says to install ntfy.
50. `[either]` Away from home (mobile data), unlink the phone: ntfy no longer lists a RollCall subscription, and marking one of that user's print requests Done from a PC shows no notification on it.
51. `[either]` On Wi-Fi at home, with the app closed, mark one of that user's print requests Done with a photo from a PC: the notification shows the photo, and expanding it shows it large. Do it again away from home (mobile data), with Cloudflare Access in front of the server: the photo shows too. Sign out in the full app and do it once more: the notification shows its text only.
52. `[google]` `google` via FCM: set up Firebase on the Settings page, choosing the downloaded service-account key file in a desktop browser, then once more in the full app on a phone: each time the field shows the file's name and the service account's email, and Save says Saved. On a `google` phone without ntfy (or any other distributor), sign in: the app restarts itself once, then Pairing says phone notifications work via Google. Tap Send a test notification: it arrives. Close the app, turn Wi-Fi off and mark one of the user's requests Done with a photo from a PC: the notification shows with the photo, and tapping it opens the request.
53. `[google]` `google` with ntfy installed uses ntfy: install ntfy on the phone from 52 and open RollCall: ntfy lists a RollCall subscription, Pairing says via ntfy, and the next notification arrives through ntfy.
54. `[foss]` `foss` via ntfy: on a `foss` phone with ntfy, steps 43 and 44 pass, and Firebase set up on the server changes nothing (no restart).
55. `[google]` Change a Firebase setting on the Settings page (or pair the `google` phone with another server): the next time the app opens signed in it restarts itself once, and FCM notifications still arrive.
56. `[foss]` `foss` QR code: on a `foss` phone, Pair with a code instead and scan the Devices page's QR code: the app asks for the camera the first time, the ZXing scanner reads the code held upright, and pairing finishes as in 3. Back out of the scanner: the app returns to Pairing with nothing scanned.

A phone without MIFARE Classic support should say so on Scan. A Pixel cannot show this, so it is covered by the web tests only.

**Web app**

*Triggers.* Web: every file of the web app outside the phone's own code (`lib/phone/`, `lib/components/phone/`, `routes/scan/`, `routes/pair/`), shared web code (above) included: the pages, their components and their logic. Server: serving the web app (`webapp.py`).

Run these in a desktop browser at the test server's address, signed in as an Admin unless a step says otherwise.

57. `[browser]` Sign in: Inventory shows the restored stock, and Spools, Products, Catalog, Requests, Review, Shopping list, Activity, Devices, Users and Settings each open with their data. Account shows **RollCall server** with the candidate's version, and no app version. Sign out: the sign-in page shows.
58. `[browser]` Add a spool by hand (Add spool), then record an action on its page: Activity shows the event. Undo it: Activity shows it undone, and the spool's page is as it was.
59. `[browser]` In a private window, sign in as a Requester and submit a print request with a model file. As the Admin, approve it with a spool held for it, then move it through to Done with a photo: the Requester's page shows each stage and the photo, and the spool's page shows the hold while the request holds it.
60. `[browser]` On Shopping list, a product below its low-stock threshold is listed with how many spools to buy. Mark it Ordered, then dismiss it and bring it back from Dismissed: its history lists each change.
61. `[browser]` Narrow the window to a phone's width (600 pixels or less): the phone layout's bottom bar replaces the side navigation, and Inventory and a spool's page fit without scrolling sideways.

**Server**

*Triggers.* Server: its source (everything under `server/src/filament_tracker/`), its migrations (`migrations/`), its dependencies and settings (`server/pyproject.toml`, `server/uv.lock`, `server/alembic.ini`, `server/.env.example`), the image's build files (`Dockerfile`, `.dockerignore`), and the deploy files (`deploy/compose.yaml`, `deploy/.env.example`, `deploy/candidate/`). Web: the versions on Account (`lib/components/account/ReleaseVersions.svelte`, `lib/release-versions.ts`, `lib/api/health.ts`).

The test server has email, Home Assistant and printers off, so it can't check them. A change to the Home Assistant link (`ha/`) or the printer link (`printer/`) also runs that link's own checklist in [server/README.md](../server/README.md), as [docs/testing.md](testing.md#manual-checklists) says; email is covered by the server's tests.

62. `[browser]` The test server, restored on the previous release and upgraded to this release candidate, answers `/api/v1/health` with the candidate's version, such as `"version": "1.4.0-rc.1"`. Signed in, Account shows **RollCall server 1.4.0-rc.1**, and the restored spools, print requests and users are there: Spools, Requests and Users list what the live server does.
63. `[browser]` The restored copy reaches nobody: Settings shows email and Home Assistant not set up and no printers, while Firebase is still set up, and Devices shows each of the live server's phones and scanners revoked or not at all.
64. `[either]` Before 48 updates the test phone, with the test server already on this release candidate: Account shows **RollCall app** with the previous release's version and **RollCall server** with the candidate's, with "This app is on an older release than the server. Update the app." when the previous release shows the server's version at all (1.4.0 and later). After 48, Account shows the candidate's version for both, and no note.
65. `[browser]` Fresh install, run last because it empties the test server, and only on a full run or when first-start setup (`api/setup.py`, `services/setup.py`, and the web app's `routes/setup/` and `lib/components/SetupForm.svelte`) or a migration (`migrations/`) changed: stop the test server's stack, remove its data volume (`rollcall-candidate_data`), and update the stack with `RESTORE=0` and the candidate as `ROLLCALL_TAG` and `CANDIDATE_TAG`. At its address, **Set up RollCall** asks for the setup code from the server's log; finish setup with a new Admin account: Inventory opens, empty, and Account shows the candidate's version. The next release candidate starts from a fresh restore, so nothing needs putting back.
