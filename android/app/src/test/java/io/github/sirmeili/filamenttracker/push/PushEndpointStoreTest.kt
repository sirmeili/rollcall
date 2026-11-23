package io.github.sirmeili.filamenttracker.push

import io.github.sirmeili.filamenttracker.storage.KeyValues
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PushEndpointStoreTest {
    private class MemoryValues : KeyValues {
        val map = mutableMapOf<String, String>()

        override fun get(name: String) = map[name]

        override fun put(name: String, value: String) {
            map[name] = value
        }

        override fun remove(name: String) {
            map.remove(name)
        }
    }

    private val values = MemoryValues()
    private val store = PushEndpointStore(values)
    private val endpoint = PushEndpointInfo("https://ntfy.example.com/upAbc", "BKey", "auth")

    @Test
    fun keepsTheLastEndpoint() {
        assertNull(store.load())

        store.save(endpoint)
        assertEquals(endpoint, store.load())

        val moved = endpoint.copy(url = "https://ntfy.example.com/upMoved")
        store.save(moved)
        assertEquals(moved, PushEndpointStore(values).load())
    }

    @Test
    fun forgetsItWhenDropped() {
        store.save(endpoint)

        store.clear()

        assertNull(store.load())
        assertEquals(emptyMap<String, String>(), values.map)
    }

    @Test
    fun aPartlyStoredEndpointReadsAsNone() {
        store.save(endpoint)
        values.remove("auth")

        assertNull(store.load())
    }

    @Test
    fun keepsAnFcmTokenWithItsRoute() {
        val token = PushEndpointInfo.fcm("fcm-token:abc")

        store.save(token)

        assertEquals(token, PushEndpointStore(values).load())
        assertEquals("fcm", PushEndpointStore(values).load()?.route)
        assertNull(token.p256dh)
    }

    @Test
    fun aWebPushEndpointIsTheDefaultRoute() {
        store.save(endpoint)

        assertEquals("web_push", store.load()?.route)
    }
}
