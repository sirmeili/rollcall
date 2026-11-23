package io.github.sirmeili.filamenttracker.push

import android.content.ContentProvider
import android.content.ContentValues
import android.content.Context
import android.database.Cursor
import android.net.Uri
import com.google.android.gms.common.ConnectionResult
import com.google.android.gms.common.GoogleApiAvailability
import com.google.firebase.FirebaseApp
import com.google.firebase.FirebaseOptions
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import io.github.sirmeili.filamenttracker.storage.PrefsValues

/**
 * Firebase started from the server's client settings, with no `google-services.json`. It
 * starts at app start (also when Android starts the app for a notification) from the settings
 * kept from the server; settings that arrive later start it at once if it isn't running, and
 * otherwise after the app restarts ([FirebaseStartup]). Firebase's own start-up provider is
 * removed in the manifest, and automatic token creation and delivery metrics export are off.
 */
object FirebaseStart {
    private fun settings(context: Context) = FirebaseSettingsStore(PrefsValues(context, "firebase"))

    /** Start Firebase from the kept settings, if there are any. */
    fun atAppStart(context: Context) {
        settings(context).load()?.let { start(context, it) }
    }

    /** Keep the server's settings; true when the app must restart to use them. */
    fun use(context: Context, wanted: FirebaseSettings?): Boolean {
        settings(context).save(wanted)
        return when (FirebaseStartup.decide(running(context), wanted)) {
            FirebaseStartup.NOTHING -> false
            FirebaseStartup.START -> {
                start(context, wanted ?: return false)
                false
            }
            FirebaseStartup.RESTART -> true
        }
    }

    fun route(context: Context, endpoints: PushEndpointStore) =
        FcmRoute(settings(context), { playServices(context) && running(context) != null }, FirebaseFcm(context), endpoints)

    fun running(context: Context): FirebaseSettings? {
        val app = FirebaseApp.getApps(context).firstOrNull { it.name == FirebaseApp.DEFAULT_APP_NAME } ?: return null
        val options = app.options
        return FirebaseSettings(options.projectId.orEmpty(), options.applicationId, options.apiKey, options.gcmSenderId.orEmpty())
    }

    private fun start(context: Context, settings: FirebaseSettings) {
        val options =
            FirebaseOptions.Builder()
                .setProjectId(settings.projectId)
                .setApplicationId(settings.appId)
                .setApiKey(settings.apiKey)
                .setGcmSenderId(settings.senderId)
                .build()
        FirebaseApp.initializeApp(context, options)
    }

    private fun playServices(context: Context) =
        GoogleApiAvailability.getInstance().isGooglePlayServicesAvailable(context) == ConnectionResult.SUCCESS
}

/** FCM's token calls through the Firebase messaging library; nothing while Firebase isn't
 * running. */
private class FirebaseFcm(private val context: Context) : FcmClient {
    private fun messaging() = FirebaseStart.running(context)?.let { FirebaseMessaging.getInstance() }

    override fun token(onToken: (String) -> Unit) {
        messaging()?.token?.addOnSuccessListener { token -> token?.let(onToken) }
    }

    override fun deleteToken() {
        messaging()?.deleteToken()
    }
}

/**
 * Starts Firebase as the app process starts, before any service or activity, in place of
 * Firebase's own provider (which reads `google-services.json`).
 */
class FirebaseStartProvider : ContentProvider() {
    override fun onCreate(): Boolean {
        context?.let { runCatching { FirebaseStart.atAppStart(it) } }
        return true
    }

    override fun query(uri: Uri, projection: Array<out String>?, selection: String?, selectionArgs: Array<out String>?, sortOrder: String?): Cursor? = null

    override fun getType(uri: Uri): String? = null

    override fun insert(uri: Uri, values: ContentValues?): Uri? = null

    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?) = 0

    override fun update(uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<out String>?) = 0
}

/**
 * What FCM tells the app, even while it is closed: a new token (passed on only while FCM is the
 * route in use) or a phone notification, shown as a UnifiedPush one is. Nothing here logs the
 * token or notification contents.
 */
class FcmService : FirebaseMessagingService() {
    override fun onNewToken(token: String) {
        FirebaseStart.route(this, pushEndpoints(this)).tokenRefreshed(token)
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val data = message.data
        val notification = PhoneNotification.of { name -> data[name] } ?: return
        Notifier(this).show(notification)
    }
}
