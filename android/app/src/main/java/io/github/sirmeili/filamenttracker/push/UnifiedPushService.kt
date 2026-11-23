package io.github.sirmeili.filamenttracker.push

import android.content.Context
import android.util.Log
import io.github.sirmeili.filamenttracker.storage.PrefsValues
import org.json.JSONObject
import org.unifiedpush.android.connector.FailedReason
import org.unifiedpush.android.connector.PushService
import org.unifiedpush.android.connector.data.PushEndpoint as UnifiedPushEndpoint
import org.unifiedpush.android.connector.data.PushMessage

/**
 * What the UnifiedPush distributor tells the app, even while it is closed: a new endpoint
 * (kept, and passed to the open app), a push (shown as a phone notification), or that this
 * phone was dropped. Nothing here logs endpoints, keys or notification contents.
 */
class UnifiedPushService : PushService() {
    private val endpoints by lazy { pushEndpoints(this) }

    override fun onNewEndpoint(endpoint: UnifiedPushEndpoint, instance: String) {
        // Without Web Push keys the server cannot encrypt for this phone, so it isn't used.
        val keys = endpoint.pubKeySet ?: return
        val info = PushEndpoint(endpoint.url, keys.pubKey, keys.auth)
        endpoints.save(info)
        PushEvents.endpointChanged(info)
    }

    override fun onMessage(message: PushMessage, instance: String) {
        // The server always encrypts (RFC 8291); anything else isn't from it.
        if (!message.decrypted) return
        val json = runCatching { JSONObject(String(message.content, Charsets.UTF_8)) }.getOrNull() ?: return
        val notification =
            PhoneNotification.of { name -> if (json.isNull(name)) null else json.optString(name) } ?: return
        Notifier(this).show(notification)
    }

    override fun onRegistrationFailed(reason: FailedReason, instance: String) {
        Log.w(TAG, "UnifiedPush registration failed: $reason")
    }

    override fun onUnregistered(instance: String) {
        endpoints.clear()
        PushEvents.endpointChanged(null)
    }

    private companion object {
        const val TAG = "RollCallPush"
    }
}

/** The stored endpoint, in its own preferences file: it is not a secret. */
fun pushEndpoints(context: Context) = PushEndpointStore(PrefsValues(context, "push-endpoint"))
