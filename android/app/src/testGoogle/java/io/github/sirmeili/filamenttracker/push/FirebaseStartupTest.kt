package io.github.sirmeili.filamenttracker.push

import org.junit.Assert.assertEquals
import org.junit.Test

/** Firebase starts once per app start: new settings start it at once when it isn't running,
 * and otherwise take effect after the app restarts. */
class FirebaseStartupTest {
    private val ours = FirebaseSettings("rollcall-test", "1:1:android:ab", "AIzaKey", "1")
    private val other = ours.copy(projectId = "other-server", senderId = "2")

    @Test
    fun theSameSettingsNeedNothing() {
        assertEquals(FirebaseStartup.NOTHING, FirebaseStartup.decide(running = ours, wanted = ours))
        assertEquals(FirebaseStartup.NOTHING, FirebaseStartup.decide(running = null, wanted = null))
    }

    @Test
    fun firstSettingsStartFirebaseAtOnce() {
        assertEquals(FirebaseStartup.START, FirebaseStartup.decide(running = null, wanted = ours))
    }

    @Test
    fun changedSettingsOrAnotherServerRestartTheApp() {
        assertEquals(FirebaseStartup.RESTART, FirebaseStartup.decide(running = ours, wanted = other))
    }

    @Test
    fun firebaseRemovedOnTheServerRestartsTheApp() {
        assertEquals(FirebaseStartup.RESTART, FirebaseStartup.decide(running = ours, wanted = null))
    }
}
