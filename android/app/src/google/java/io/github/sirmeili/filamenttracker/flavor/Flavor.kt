package io.github.sirmeili.filamenttracker.flavor

import android.app.Activity
import android.content.Context
import android.content.Intent
import com.getcapacitor.JSObject
import com.getcapacitor.PluginCall
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import io.github.sirmeili.filamenttracker.push.FirebaseSettings
import io.github.sirmeili.filamenttracker.push.FirebaseStart
import io.github.sirmeili.filamenttracker.push.PushEndpointStore
import io.github.sirmeili.filamenttracker.push.UnifiedPushProvider
import io.github.sirmeili.filamenttracker.push.googleRoutes

/** The `google` flavor: phone notifications through a UnifiedPush distributor, else Google's
 * push service (FCM) when the server has Firebase set up; QR codes through Google's code
 * scanner. */
val appFlavor: AppFlavor =
    object : AppFlavor {
        override fun pushRoutes(context: Context, endpoints: PushEndpointStore) =
            googleRoutes(UnifiedPushProvider(context, endpoints), FirebaseStart.route(context, endpoints))

        override fun useFirebase(context: Context, settings: FirebaseSettings?) = FirebaseStart.use(context, settings)

        override val qrScanner: QrScanner = GmsQrScanner
    }

/** Google's code scanner (Play services), which needs no camera permission and keeps camera
 * code out of the app. */
private object GmsQrScanner : QrScanner {
    override fun start(activity: Activity, call: PluginCall): Intent? {
        val options = GmsBarcodeScannerOptions.Builder().setBarcodeFormats(Barcode.FORMAT_QR_CODE).build()
        GmsBarcodeScanning.getClient(activity, options)
            .startScan()
            .addOnSuccessListener { code -> call.resolve(JSObject().put("value", code.rawValue)) }
            .addOnCanceledListener { call.resolve(JSObject().put("value", null)) }
            .addOnFailureListener { call.reject("camera unavailable") }
        return null
    }

    override fun result(resultCode: Int, data: Intent?): String? = null
}
