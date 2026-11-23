package io.github.sirmeili.filamenttracker.push

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.webkit.CookieManager
import io.github.sirmeili.filamenttracker.storage.KeystoreKey
import io.github.sirmeili.filamenttracker.storage.PrefsValues
import io.github.sirmeili.filamenttracker.storage.SecureStore
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL

/**
 * Downloads a phone notification's photo as the web app's calls reach the server: the paired
 * server's address and Access token from the encrypted storage the web app keeps them in, and
 * the signed-in session's cookie from the web view's cookies. Any failure (signed out, away
 * without Access, a timeout, not a photo) gives null, and the notification shows its text only.
 * Nothing here logs the cookie, the token or the photo.
 */
class PhotoDownloader(private val context: Context) {
    /** The photo at `photo` (a path on the server), scaled to fit a notification, or null. */
    fun download(photo: String): Bitmap? = runCatching { fetch(photo) }.getOrNull()

    private fun fetch(photo: String): Bitmap? {
        val store = SecureStore(KeystoreKey::get, PrefsValues(context))
        val server = store.get(PAIRING_KEY)?.let { JSONObject(it).optString("url") }
        val access =
            store.get(ACCESS_KEY)?.let {
                val json = JSONObject(it)
                AccessToken(json.getString("clientId"), json.getString("clientSecret"))
            }
        val cookie = server?.let { CookieManager.getInstance().getCookie(it) }
        val request = PhotoRequest.of(server, photo, cookie, access) ?: return null
        val connection = URL(request.url).openConnection() as HttpURLConnection
        try {
            // A redirect is Access's sign-in page or another site: never follow it with the cookie.
            connection.instanceFollowRedirects = false
            connection.connectTimeout = TIMEOUT_MS
            connection.readTimeout = TIMEOUT_MS
            request.headers.forEach(connection::setRequestProperty)
            if (connection.responseCode != HttpURLConnection.HTTP_OK) return null
            if (connection.contentType?.startsWith("image/") != true) return null
            val bytes = connection.inputStream.use(::readAtMost) ?: return null
            return decode(bytes)
        } finally {
            connection.disconnect()
        }
    }

    /** The whole body, or null if it is larger than any photo the server keeps. */
    private fun readAtMost(input: InputStream): ByteArray? {
        val out = ByteArrayOutputStream()
        val buffer = ByteArray(BUFFER_BYTES)
        while (true) {
            val read = input.read(buffer)
            if (read < 0) return out.toByteArray()
            out.write(buffer, 0, read)
            if (out.size() > MAX_BYTES) return null
        }
    }

    /** The photo, shrunk by a power of two until its longer side is at most [MAX_SIDE]. */
    private fun decode(bytes: ByteArray): Bitmap? {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
        var sample = 1
        while (maxOf(bounds.outWidth, bounds.outHeight) / sample > MAX_SIDE) sample *= 2
        return BitmapFactory.decodeByteArray(bytes, 0, bytes.size, BitmapFactory.Options().apply { inSampleSize = sample })
    }

    private companion object {
        // The web app's keys for the pairing and the Access token (web/src/lib/phone/pairing-store.ts).
        const val PAIRING_KEY = "pairing"
        const val ACCESS_KEY = "cf_access"
        const val TIMEOUT_MS = 10_000
        const val BUFFER_BYTES = 64 * 1024
        const val MAX_BYTES = 20 * 1024 * 1024
        const val MAX_SIDE = 1440
    }
}
