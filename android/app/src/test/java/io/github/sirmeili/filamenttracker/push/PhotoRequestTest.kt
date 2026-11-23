package io.github.sirmeili.filamenttracker.push

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PhotoRequestTest {
    private val photo = "/api/v1/requests/7/photos/abc"
    private val token = AccessToken("id.access", "secret")

    @Test
    fun downloadsFromThePairedServerWithTheSessionAndAccessToken() {
        val request = PhotoRequest.of("https://rollcall.example.com/", photo, "session=s1", token)

        assertEquals("https://rollcall.example.com/api/v1/requests/7/photos/abc", request?.url)
        assertEquals(
            mapOf(
                "Cookie" to "session=s1",
                "CF-Access-Client-Id" to "id.access",
                "CF-Access-Client-Secret" to "secret",
            ),
            request?.headers,
        )
    }

    @Test
    fun sendsTheAccessTokenOnlyOverHttps() {
        val request = PhotoRequest.of("http://192.168.1.20:8000", photo, "session=s1", token)

        assertEquals("http://192.168.1.20:8000$photo", request?.url)
        assertEquals(mapOf("Cookie" to "session=s1"), request?.headers)
    }

    @Test
    fun sendsNoAccessTokenWhenTheServerHasNone() {
        val request = PhotoRequest.of("https://rollcall.example.com", photo, "session=s1", null)

        assertEquals(mapOf("Cookie" to "session=s1"), request?.headers)
    }

    @Test
    fun downloadsNothingSignedOutOrUnpaired() {
        assertNull(PhotoRequest.of("https://rollcall.example.com", photo, null, token))
        assertNull(PhotoRequest.of("https://rollcall.example.com", photo, "", token))
        assertNull(PhotoRequest.of(null, photo, "session=s1", token))
        assertNull(PhotoRequest.of("ftp://rollcall.example.com", photo, "session=s1", token))
    }
}
