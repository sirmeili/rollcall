# The phone app is Capacitor around the web app, with a Kotlin NFC plugin

Browser NFC reads only NDEF, so it cannot read the MIFARE Classic blocks on Bambu tags. The phone app wraps the same web app build in Capacitor and adds a Kotlin plugin using Android's `MifareClassic`. It uses Capacitor's native HTTP, so the server needs no CORS.
