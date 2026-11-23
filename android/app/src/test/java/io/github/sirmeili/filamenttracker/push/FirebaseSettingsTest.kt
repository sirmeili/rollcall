package io.github.sirmeili.filamenttracker.push

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** The Firebase client settings as the server's push configuration gives them. */
class FirebaseSettingsTest {
    private val server =
        mapOf(
            "project_id" to "rollcall-test",
            "app_id" to "1:1:android:ab",
            "api_key" to "AIzaKey",
            "sender_id" to "1",
        )

    @Test
    fun readsTheServersFourSettings() {
        assertEquals(
            FirebaseSettings("rollcall-test", "1:1:android:ab", "AIzaKey", "1"),
            FirebaseSettings.fromServer(server::get),
        )
    }

    @Test
    fun isNoneWhenAnyIsMissing() {
        for (missing in server.keys) {
            val given = server - missing
            assertNull(missing, FirebaseSettings.fromServer(given::get))
        }
    }
}
