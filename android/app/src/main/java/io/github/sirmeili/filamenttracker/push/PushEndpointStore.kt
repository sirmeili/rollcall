package io.github.sirmeili.filamenttracker.push

import io.github.sirmeili.filamenttracker.storage.KeyValues

/**
 * Where a push service delivers this phone's notifications, as the route gave it, named by the
 * server's [route]: a Web Push URL with its keys (base64url), or an FCM registration token in
 * [url] with no keys.
 */
data class PushEndpointInfo(
    val url: String,
    val p256dh: String?,
    val auth: String?,
    val route: String = WEB_PUSH,
) {
    companion object {
        const val WEB_PUSH = "web_push"
        const val FCM = "fcm"

        fun fcm(token: String) = PushEndpointInfo(token, null, null, FCM)
    }
}

/**
 * The endpoint the route last gave, kept so the web app can send it to the server when the
 * user next signs in, even if it changed while the app was closed.
 */
class PushEndpointStore(private val values: KeyValues) {
    fun load(): PushEndpointInfo? {
        val url = values.get(URL) ?: return null
        val route = values.get(ROUTE) ?: PushEndpointInfo.WEB_PUSH
        if (route == PushEndpointInfo.FCM) return PushEndpointInfo.fcm(url)
        val p256dh = values.get(P256DH) ?: return null
        val auth = values.get(AUTH) ?: return null
        return PushEndpointInfo(url, p256dh, auth)
    }

    fun save(endpoint: PushEndpointInfo) {
        clear()
        values.put(URL, endpoint.url)
        values.put(ROUTE, endpoint.route)
        endpoint.p256dh?.let { values.put(P256DH, it) }
        endpoint.auth?.let { values.put(AUTH, it) }
    }

    fun clear() = listOf(URL, ROUTE, P256DH, AUTH).forEach(values::remove)

    private companion object {
        const val URL = "url"
        const val ROUTE = "route"
        const val P256DH = "p256dh"
        const val AUTH = "auth"
    }
}
