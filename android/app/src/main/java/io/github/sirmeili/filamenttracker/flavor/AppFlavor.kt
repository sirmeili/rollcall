package io.github.sirmeili.filamenttracker.flavor

import android.app.Activity
import android.content.Context
import android.content.Intent
import com.getcapacitor.PluginCall
import io.github.sirmeili.filamenttracker.push.FirebaseSettings
import io.github.sirmeili.filamenttracker.push.PushEndpointStore
import io.github.sirmeili.filamenttracker.push.PushRoutes

/**
 * What differs between the two app flavors (android/README.md, Flavors). Each flavor's source
 * set defines `appFlavor`: `google` with Google's services, `foss` with no Google code.
 */
interface AppFlavor {
    /** The phone notification routes this flavor can use, in order of preference. */
    fun pushRoutes(context: Context, endpoints: PushEndpointStore): PushRoutes

    /**
     * Use the Firebase client settings the server gave (null: the server has none). True when
     * the app must restart for them to take effect.
     */
    fun useFirebase(context: Context, settings: FirebaseSettings?): Boolean

    val qrScanner: QrScanner
}

/** Scanning a QR code with the camera. */
interface QrScanner {
    /** Start a scan for [call]: either answer it here and return null, or return the activity
     * to start, whose result [result] reads. */
    fun start(activity: Activity, call: PluginCall): Intent?

    /** The scanned text from the started activity's result; null when the user backed out. */
    fun result(resultCode: Int, data: Intent?): String?
}
