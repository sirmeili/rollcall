package io.github.sirmeili.filamenttracker.push

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Test

class PushEventsTest {
    private val endpoint = PushEndpoint("https://ntfy.example.com/upAbc", "BKey", "auth")

    @After
    fun stopListening() {
        PushEvents.listen(null)
    }

    @Test
    fun passesEachChangedEndpointToTheListener() {
        val seen = mutableListOf<PushEndpoint?>()
        PushEvents.listen { seen += it }

        PushEvents.endpointChanged(endpoint)
        PushEvents.endpointChanged(null)

        assertEquals(listOf(endpoint, null), seen)
    }

    @Test
    fun aChangeWithNobodyListeningIsDropped() {
        // The app isn't open: it reads the stored endpoint when it next registers.
        PushEvents.endpointChanged(endpoint)

        val seen = mutableListOf<PushEndpoint?>()
        PushEvents.listen { seen += it }
        assertEquals(emptyList<PushEndpoint?>(), seen)
    }
}
