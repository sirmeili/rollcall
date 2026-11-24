package io.github.sirmeili.filamenttracker.push

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PhoneNotificationTest {
    private fun fields(vararg pairs: Pair<String, String>): (String) -> String? = pairs.toMap()::get

    @Test
    fun readsThePayloadTheServerSends() {
        val read =
            PhoneNotification.of(
                fields(
                    "kind" to "request_update",
                    "title" to "Your print is done",
                    "text" to "Benchy is done.",
                    "path" to "/requests/7",
                ),
            )

        assertEquals(PhoneNotification("request_update", "Your print is done", "Benchy is done.", "/requests/7"), read)
    }

    @Test
    fun readsThePhotoToShow() {
        val read =
            PhoneNotification.of(
                fields(
                    "kind" to "new_photo",
                    "title" to "New photo of your print",
                    "path" to "/requests/7",
                    "photo" to "/api/v1/requests/7/photos/abc",
                ),
            )

        assertEquals("/api/v1/requests/7/photos/abc", read?.photo)
    }

    @Test
    fun showsNoPhotoUnlessItIsOnThisServer() {
        assertNull(PhoneNotification.of(fields("title" to "Done"))?.photo)
        for (outside in listOf("https://evil.example.com/x.jpg", "//evil.example.com/x.jpg", "/\\evil.example.com", "x.jpg", "")) {
            assertNull(outside, PhoneNotification.of(fields("title" to "Done", "photo" to outside))?.photo)
        }
    }

    @Test
    fun needsATitle() {
        assertNull(PhoneNotification.of(fields("kind" to "low_stock", "text" to "x", "path" to "/")))
        assertNull(PhoneNotification.of(fields("kind" to "low_stock", "title" to "", "path" to "/")))
    }

    @Test
    fun opensTheHomePageWithoutAPathOrKind() {
        val read = PhoneNotification.of(fields("title" to "Hello"))

        assertEquals(PhoneNotification("", "Hello", "", "/"), read)
    }

    @Test
    fun opensOnlyPagesOfThisApp() {
        for (outside in listOf("https://evil.example.com/", "//evil.example.com/x", "/\\evil.example.com", "requests/7", "")) {
            assertEquals(outside, "/", PhoneNotification.safePath(outside))
        }
        assertEquals("/", PhoneNotification.safePath(null))
        assertEquals("/requests/7?tab=photos", PhoneNotification.safePath("/requests/7?tab=photos"))
    }
}
