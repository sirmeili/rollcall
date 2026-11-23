# Phone notifications go through official FCM, set up on the server, or UnifiedPush, in two app flavors

Phone notifications reach a user's phone by documented routes only, in two builds of the app released together from one package name and signing key (#81, #223):

- **`google`** uses Google's official push service, Firebase Cloud Messaging, when the server owner has set up Firebase on the Settings page (or in `.env`, ADR-0007). The phone gets Firebase's client settings with its push configuration and starts Firebase from them at app start, with no `google-services.json`, no Analytics, automatic token creation and delivery-metrics export off. The server sends with the HTTP v1 API and an OAuth token from the service-account key, stored encrypted. A UnifiedPush distributor such as ntfy, if installed, is preferred over FCM.
- **`foss`** contains no Google code: no Firebase, no Play services and not Google's QR code scanner either: it scans with ZXing instead. The owner decided this while #227 was built (recorded on #227), because Google's code scanner is Play services code, which `foss` can't hold. It gets phone notifications only through a UnifiedPush distributor. CI fails if its dependencies hold any Google service.

Why, from #81 and its grilling (2026-11-22):

- **One public APK must work with any server.** The app is released publicly through GitHub Releases, and every owner runs their own server. FCM ties an app to one Firebase project through its `google-services.json`, so a project built into the APK would make every server send through the maintainer's project. Starting Firebase from settings the server hands out lets each owner use their own project with the same APK.
- **Family members should only have to update the app.** On a phone with Google Play, FCM needs nothing else installed, which is what the owner's brother, who rarely visits, can do (user stories 12 and 13).
- **The undocumented embedded FCM distributor was rejected.** UnifiedPush's embedded FCM distributor would give `google` phones FCM without the owner setting up Firebase, but it isn't a documented route, and #81 allows documented routes only, so neither flavor uses it.
- **`foss` keeps a no-Google build** for phones without Google Play and for people who avoid Google (user story 14), and `google` respects an installed distributor for the same reason (user story 15).

## Consequences

- Each owner who wants FCM creates a Firebase project and enters five settings (`docs/deploy.md`, Firebase). Without them, phones need a distributor.
- Firebase starts once per app process, so changed Firebase settings, or pairing with another server, take effect after an app restart, which the app does itself when it has to.
- The FCM token is one more phone endpoint kind (route `fcm`) beside Web Push, with the same payload, the same failure rules and the same fake push outbox in tests. FCM messages aren't end-to-end encrypted as Web Pushes are: Google sees their text.
- The server asks Google for OAuth tokens with an assertion it signs itself, using the `cryptography` package it already has, rather than adding Google's auth library. The token endpoint is fixed in the code, never read from the key file.
- `foss` scans QR codes in the app with ZXing, so it asks for the camera permission, which `google` doesn't need.
