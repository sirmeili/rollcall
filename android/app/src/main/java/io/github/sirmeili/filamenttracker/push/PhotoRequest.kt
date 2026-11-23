package io.github.sirmeili.filamenttracker.push

/** The Cloudflare Access service token the phone sends to pass Access in front of the server
 * away from home, as the web app keeps it (`cf_access`). */
data class AccessToken(val clientId: String, val clientSecret: String)

/**
 * Where a phone notification's photo is downloaded from, and with what: the paired server, the
 * signed-in session's cookie and, only over HTTPS, the Access token, as the web app's own calls
 * send them. The server then serves the photo only to someone who may see its request.
 */
data class PhotoRequest(val url: String, val headers: Map<String, String>) {
    companion object {
        /** The download of `photo` (a path on the server), or null when the phone isn't paired
         * with an HTTP(S) server or isn't signed in. */
        fun of(server: String?, photo: String, cookie: String?, access: AccessToken?): PhotoRequest? {
            val base = server?.trimEnd('/') ?: return null
            val https = base.startsWith("https://", ignoreCase = true)
            if (!https && !base.startsWith("http://", ignoreCase = true)) return null
            if (cookie.isNullOrEmpty()) return null
            val headers = mutableMapOf("Cookie" to cookie)
            if (https && access != null) {
                headers["CF-Access-Client-Id"] = access.clientId
                headers["CF-Access-Client-Secret"] = access.clientSecret
            }
            return PhotoRequest(base + photo, headers)
        }
    }
}
