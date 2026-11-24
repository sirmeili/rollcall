package io.github.sirmeili.filamenttracker.flavor

import android.app.Activity
import android.content.Context
import android.content.Intent
import com.getcapacitor.PluginCall
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanIntentResult
import com.journeyapps.barcodescanner.ScanOptions
import io.github.sirmeili.filamenttracker.push.FirebaseSettings
import io.github.sirmeili.filamenttracker.push.PushEndpointStore
import io.github.sirmeili.filamenttracker.push.PushRoutes
import io.github.sirmeili.filamenttracker.push.UnifiedPushProvider

/** The `foss` flavor: no Google code. Phone notifications come only through a UnifiedPush
 * distributor, and QR codes are scanned with ZXing, in the app, with the camera permission. */
val appFlavor: AppFlavor =
    object : AppFlavor {
        override fun pushRoutes(context: Context, endpoints: PushEndpointStore) =
            PushRoutes(listOf(UnifiedPushProvider(context, endpoints)))

        // No FCM here, so the server's Firebase settings are never used.
        override fun useFirebase(context: Context, settings: FirebaseSettings?) = false

        override val qrScanner: QrScanner = ZxingQrScanner
    }

/** ZXing's scanner (zxing-android-embedded, Apache-2.0), which asks for the camera itself. */
private object ZxingQrScanner : QrScanner {
    override fun start(activity: Activity, call: PluginCall): Intent =
        ScanContract().createIntent(
            activity,
            ScanOptions()
                .setDesiredBarcodeFormats(ScanOptions.QR_CODE)
                .setPrompt("Point the camera at the QR code")
                .setBeepEnabled(false)
                .setOrientationLocked(false),
        )

    override fun result(resultCode: Int, data: Intent?): String? =
        ScanIntentResult.parseActivityResult(resultCode, data).contents
}
