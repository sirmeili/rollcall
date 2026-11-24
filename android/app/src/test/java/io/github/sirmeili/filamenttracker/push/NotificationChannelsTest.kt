package io.github.sirmeili.filamenttracker.push

import org.junit.Assert.assertEquals
import org.junit.Test

class NotificationChannelsTest {
    @Test
    fun eachKindHasItsOwnChannel() {
        val kinds =
            listOf(
                "new_request",
                "request_update",
                "new_photo",
                "low_stock",
                "suggestion",
                "nearly_out",
                "backup_failed",
                "test",
            )

        val channels = kinds.map(NotificationChannels::of)

        assertEquals(kinds, channels.map { it.id })
        assertEquals(kinds.size, channels.map { it.name }.toSet().size)
        assertEquals("Request updates", NotificationChannels.of("request_update").name)
    }

    @Test
    fun aKindTheAppDoesNotKnowYetStillShows() {
        assertEquals(NotificationChannels.OTHER, NotificationChannels.of("something_new"))
        assertEquals(NotificationChannels.OTHER, NotificationChannels.of(""))
    }

    @Test
    fun listsEveryChannelToCreateOnce() {
        val ids = NotificationChannels.ALL.map { it.id }

        assertEquals(ids.toSet().size, ids.size)
        assertEquals("other", ids.last())
        assertEquals(9, ids.size)
    }
}
