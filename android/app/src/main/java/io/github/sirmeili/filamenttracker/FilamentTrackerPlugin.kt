package io.github.sirmeili.filamenttracker

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.nfc.NfcAdapter
import android.nfc.Tag
import android.nfc.tech.MifareClassic
import androidx.activity.result.ActivityResult
import androidx.core.app.NotificationManagerCompat
import com.getcapacitor.JSArray
import com.getcapacitor.JSObject
import com.getcapacitor.PermissionState
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import com.getcapacitor.annotation.ActivityCallback
import com.getcapacitor.annotation.Permission
import com.getcapacitor.annotation.PermissionCallback
import io.github.sirmeili.filamenttracker.flavor.appFlavor
import io.github.sirmeili.filamenttracker.nfc.AndroidMifare
import io.github.sirmeili.filamenttracker.nfc.Hex
import io.github.sirmeili.filamenttracker.nfc.NfcState
import io.github.sirmeili.filamenttracker.nfc.TagReader
import io.github.sirmeili.filamenttracker.push.FirebaseSettings
import io.github.sirmeili.filamenttracker.push.Notifier
import io.github.sirmeili.filamenttracker.push.PhoneNotification
import io.github.sirmeili.filamenttracker.push.PushEndpointInfo
import io.github.sirmeili.filamenttracker.push.PushEvents
import io.github.sirmeili.filamenttracker.push.PushRoutes
import io.github.sirmeili.filamenttracker.push.UnifiedPushProvider
import io.github.sirmeili.filamenttracker.push.pushEndpoints
import io.github.sirmeili.filamenttracker.storage.KeystoreKey
import io.github.sirmeili.filamenttracker.storage.PrefsValues
import io.github.sirmeili.filamenttracker.storage.SecureStore

/** Android 13's permission to show notifications, as the plugin names it to Capacitor. */
private const val NOTIFICATIONS = "notifications"

/**
 * The phone app's native side: NFC tag reads, QR scanning, encrypted storage, and phone
 * notifications (the push route and its name, registering, the endpoint, Android's permission to
 * show them and tapped notifications).
 *
 * Derived keys stay in [TagReader]; only the UID, data blocks and `readOk` reach the web view.
 * Nothing here logs tag contents, the salt or stored values.
 */
@CapacitorPlugin(
    name = "FilamentTracker",
    permissions = [Permission(strings = [Manifest.permission.POST_NOTIFICATIONS], alias = NOTIFICATIONS)],
)
class FilamentTrackerPlugin : Plugin() {
    private val store by lazy { SecureStore(KeystoreKey::get, PrefsValues(context)) }
    private val endpoints by lazy { pushEndpoints(context) }
    private val routes by lazy { appFlavor.pushRoutes(context, endpoints) }
    private var pending: PluginCall? = null
    private var salt: ByteArray? = null

    private val unifiedPush by lazy { UnifiedPushProvider(context, endpoints) }

    private companion object {
        const val TONE_VOLUME = 80
        const val TONE_MS = 150
        val READ_OK_BUZZ = longArrayOf(0, 80)
        val READ_FAILED_BUZZ = longArrayOf(0, 60, 80, 60)
    }

    @PluginMethod
    fun appInfo(call: PluginCall) {
        val info = context.packageManager.getPackageInfo(context.packageName, 0)
        call.resolve(JSObject().put("version", info.versionName ?: "unknown"))
    }

    @PluginMethod
    fun nfcStatus(call: PluginCall) {
        call.resolve(JSObject().put("status", status()))
    }

    private fun status(): String {
        val adapter = NfcAdapter.getDefaultAdapter(context)
        val mifare = context.packageManager.hasSystemFeature(NfcState.MIFARE_FEATURE)
        return NfcState.of(adapter != null, mifare, adapter?.isEnabled == true)
    }

    /** Wait for the next tag. Only one read waits at a time; a newer one replaces it. */
    @PluginMethod(returnType = PluginMethod.RETURN_PROMISE)
    fun readTag(call: PluginCall) {
        val saltBytes =
            runCatching { Hex.decode(call.getString("salt").orEmpty()) }.getOrNull()
                ?.takeIf { it.isNotEmpty() }
                ?: return call.reject("salt must be hex")
        if (NfcAdapter.getDefaultAdapter(context) == null) return call.reject("no NFC")
        synchronized(this) {
            pending?.reject("replaced by a newer read")
            call.setKeepAlive(true)
            pending = call
            salt = saltBytes
        }
        activity.runOnUiThread { startReader(activity) }
    }

    @PluginMethod
    fun cancelRead(call: PluginCall) {
        take()?.reject("cancelled")
        call.resolve()
    }

    /**
     * Reader mode stays on while the app is in front, and tags that arrive while no read is
     * waiting are ignored. Android reports a tag once when it comes near, so a spool left on
     * the phone is not read again; it has to be lifted and tapped. Reader mode also keeps
     * Android's own tag handling away, and its "tag found" sound is off: that sound plays
     * before the read is done, so the app beeps only once the whole tag has been read.
     */
    private fun startReader(activity: Activity) {
        NfcAdapter.getDefaultAdapter(activity)?.enableReaderMode(
            activity,
            ::onTag,
            NfcAdapter.FLAG_READER_NFC_A or
                NfcAdapter.FLAG_READER_SKIP_NDEF_CHECK or
                NfcAdapter.FLAG_READER_NO_PLATFORM_SOUNDS,
            null,
        )
    }

    private fun onTag(tag: Tag) {
        val key = synchronized(this) { salt } ?: return
        val result =
            runCatching {
                val mifare = MifareClassic.get(tag) ?: error("not a MIFARE Classic tag")
                TagReader.read(AndroidMifare(mifare), key)
            }
        // A failed read (tag pulled away, wrong tag) rejects; the Scan page asks again.
        val call = take() ?: return
        result.fold(
            onSuccess = { read ->
                beep(ToneGenerator.TONE_PROP_ACK)
                call.resolve(
                    JSObject()
                        .put("tagUid", read.tagUid)
                        .put("blocks", JSArray(read.blocks))
                        .put("readOk", read.readOk),
                )
            },
            onFailure = {
                beep(ToneGenerator.TONE_PROP_NACK)
                call.reject("tag read failed")
            },
        )
    }

    private var tones: ToneGenerator? = null

    /**
     * Say a read is done: a beep at the notification volume, and a vibration so it is felt
     * even with the sound off. A failed read gets another tone and two short buzzes.
     */
    private fun beep(tone: Int) {
        runCatching {
            val generator = tones ?: ToneGenerator(AudioManager.STREAM_NOTIFICATION, TONE_VOLUME).also { tones = it }
            generator.startTone(tone, TONE_MS)
        }
        runCatching { buzz(if (tone == ToneGenerator.TONE_PROP_ACK) READ_OK_BUZZ else READ_FAILED_BUZZ) }
    }

    private fun buzz(pattern: LongArray) {
        val vibrator =
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                context.getSystemService(VibratorManager::class.java)?.defaultVibrator
            } else {
                @Suppress("DEPRECATION")
                context.getSystemService(Vibrator::class.java)
            } ?: return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vibrator.vibrate(VibrationEffect.createWaveform(pattern, -1))
        } else {
            @Suppress("DEPRECATION")
            vibrator.vibrate(pattern, -1)
        }
    }

    /** Take the waiting call, if any. Reader mode stays on. */
    private fun take(): PluginCall? {
        val call =
            synchronized(this) {
                val current = pending
                pending = null
                salt = null
                current
            }
        call?.setKeepAlive(false)
        return call
    }

    override fun handleOnResume() {
        super.handleOnResume()
        startReader(activity)
    }

    override fun handleOnPause() {
        NfcAdapter.getDefaultAdapter(activity)?.disableReaderMode(activity)
        super.handleOnPause()
    }

    override fun handleOnDestroy() {
        tones?.release()
        tones = null
        PushEvents.listen(null)
        super.handleOnDestroy()
    }

    override fun load() {
        super.load()
        PushEvents.listen { endpoint -> notifyListeners("pushEndpoint", JSObject().put("endpoint", endpoint?.toJs())) }
        opened(activity?.intent)
    }

    override fun handleOnNewIntent(intent: Intent) {
        super.handleOnNewIntent(intent)
        opened(intent)
    }

    /** A tapped phone notification opened the app: tell the web app its page, once, even if
     * it isn't listening yet. */
    private fun opened(intent: Intent?) {
        val path = intent?.getStringExtra(Notifier.EXTRA_PATH) ?: return
        intent.removeExtra(Notifier.EXTRA_PATH)
        notifyListeners("notificationOpened", JSObject().put("path", PhoneNotification.safePath(path)), true)
    }

    @PluginMethod
    fun pushRoute(call: PluginCall) {
        call.resolve(JSObject().put("route", routes.route()))
    }

    @PluginMethod
    fun pushRegister(call: PluginCall) {
        val vapidKey = call.getString("vapidKey")?.takeIf { it.isNotEmpty() } ?: return call.reject("vapidKey required")
        runCatching { routes.register(vapidKey) }
            .onSuccess { call.resolve() }
            .onFailure { call.reject("push registration failed") }
    }

    @PluginMethod
    fun pushUnregister(call: PluginCall) {
        runCatching { routes.unregister() }
        call.resolve()
    }

    @PluginMethod
    fun pushEndpoint(call: PluginCall) {
        call.resolve(JSObject().put("endpoint", endpoints.load()?.toJs()))
    }


    /** Whether RollCall may show notifications: Android 13's permission granted, and
     * notifications not turned off for the app in Android's settings. */
    @PluginMethod
    fun pushPermission(call: PluginCall) {
        call.resolve(permission())
    }

    /** Ask for Android 13's permission to show notifications. Earlier Android versions have
     * none to ask, and say only whether notifications are turned on. */
    @PluginMethod
    fun requestPushPermission(call: PluginCall) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU || getPermissionState(NOTIFICATIONS) == PermissionState.GRANTED) {
            return call.resolve(permission())
        }
        requestPermissionForAlias(NOTIFICATIONS, call, "permissionAnswered")
    }

    @PermissionCallback
    private fun permissionAnswered(call: PluginCall) {
        call.resolve(permission())
    }

    private fun permission(): JSObject {
        val granted = NotificationManagerCompat.from(context).areNotificationsEnabled()
        return JSObject().put("permission", if (granted) "granted" else "denied")
    }

    /** The name people know the route by: the UnifiedPush distributor app's ("ntfy"), or
     * "Google" for Google's push service (FCM). */
    @PluginMethod
    fun pushRouteName(call: PluginCall) {
        val name =
            when (routes.route()) {
                UnifiedPushProvider.ROUTE -> unifiedPush.distributorName()
                PushRoutes.FCM -> "Google"
                else -> null
            }
        call.resolve(JSObject().put("name", name))
    }

    private fun PushEndpointInfo.toJs(): JSObject =
        JSObject().put("route", route).put("url", url).put("p256dh", p256dh).put("auth", auth)

    /**
     * Use the server's Firebase client settings (absent: none), before choosing a route. When
     * they differ from the ones Firebase is running with, the app restarts itself to use them.
     */
    @PluginMethod
    fun pushConfigure(call: PluginCall) {
        val firebase = call.getObject("firebase")?.let(::firebaseSettings)
        if (!appFlavor.useFirebase(context, firebase)) return call.resolve()
        call.resolve(JSObject().put("restarting", true))
        restart()
    }

    private fun firebaseSettings(json: JSObject): FirebaseSettings? {
        val values = listOf("project_id", "app_id", "api_key", "sender_id").map { json.getString(it) ?: return null }
        return FirebaseSettings(values[0], values[1], values[2], values[3])
    }

    /** Start the app afresh in a new process, as Firebase starts once per process. */
    private fun restart() {
        val launch = context.packageManager.getLaunchIntentForPackage(context.packageName) ?: return
        context.startActivity(Intent.makeRestartActivityTask(launch.component))
        Runtime.getRuntime().exit(0)
    }

    // Each flavor has its own scanner (Flavors in android/README.md): some answer the call
    // themselves, others start an activity whose result comes back to qrScanned.
    @PluginMethod
    fun scanQr(call: PluginCall) {
        val intent = appFlavor.qrScanner.start(activity, call) ?: return
        startActivityForResult(call, intent, "qrScanned")
    }

    @ActivityCallback
    private fun qrScanned(call: PluginCall?, result: ActivityResult) {
        call?.resolve(JSObject().put("value", appFlavor.qrScanner.result(result.resultCode, result.data)))
    }

    @PluginMethod
    fun secureGet(call: PluginCall) {
        val name = call.getString("key") ?: return call.reject("key required")
        call.resolve(JSObject().put("value", store.get(name)))
    }

    @PluginMethod
    fun secureSet(call: PluginCall) {
        val name = call.getString("key") ?: return call.reject("key required")
        val value = call.getString("value") ?: return call.reject("value required")
        store.set(name, value)
        call.resolve()
    }

    @PluginMethod
    fun secureRemove(call: PluginCall) {
        val name = call.getString("key") ?: return call.reject("key required")
        store.remove(name)
        call.resolve()
    }
}
