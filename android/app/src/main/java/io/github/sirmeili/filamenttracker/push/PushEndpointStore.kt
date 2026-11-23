package io.github.sirmeili.filamenttracker.push

import io.github.sirmeili.filamenttracker.storage.KeyValues

/** Where a push service delivers this phone's notifications, with its Web Push keys
 * (base64url), as the route gave them. */
data class PushEndpointInfo(val url: String, val p256dh: String, val auth: String)

/**
 * The endpoint the route last gave, kept so the web app can send it to the server when the
 * user next signs in, even if it changed while the app was closed.
 */
class PushEndpointStore(private val values: KeyValues) {
    fun load(): PushEndpointInfo? {
        val url = values.get(URL) ?: return null
        val p256dh = values.get(P256DH) ?: return null
        val auth = values.get(AUTH) ?: return null
        return PushEndpointInfo(url, p256dh, auth)
    }

    fun save(endpoint: PushEndpointInfo) {
        values.put(URL, endpoint.url)
        values.put(P256DH, endpoint.p256dh)
        values.put(AUTH, endpoint.auth)
    }

    fun clear() = listOf(URL, P256DH, AUTH).forEach(values::remove)

    private companion object {
        const val URL = "url"
        const val P256DH = "p256dh"
        const val AUTH = "auth"
    }
}
