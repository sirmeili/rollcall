package io.github.sirmeili.filamenttracker.push

import io.github.sirmeili.filamenttracker.storage.KeyValues
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class FirebaseSettingsStoreTest {
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
    private val store = FirebaseSettingsStore(values)
    private val settings = FirebaseSettings("rollcall-test", "1:1:android:ab", "AIzaKey", "1")

    @Test
    fun keepsTheServersSettingsForTheNextAppStart() {
        assertNull(store.load())

        store.save(settings)

        assertEquals(settings, FirebaseSettingsStore(values).load())
    }

    @Test
    fun noSettingsForgetsThem() {
        store.save(settings)

        store.save(null)

        assertNull(store.load())
        assertEquals(emptyMap<String, String>(), values.map)
    }

    @Test
    fun partlyStoredSettingsReadAsNone() {
        store.save(settings)
        values.map.remove("sender_id")

        assertNull(store.load())
    }
}
