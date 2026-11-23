package io.github.sirmeili.filamenttracker.push

import io.github.sirmeili.filamenttracker.storage.KeyValues
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class FcmRouteTest {
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

    /** Firebase's token calls, answered at once. */
    private class FakeFcm(var token: String = "fcm-token:1") : FcmClient {
        var deleted = 0

        override fun token(onToken: (String) -> Unit) = onToken(token)

        override fun deleteToken() {
            deleted += 1
        }
    }

    private val settings = FirebaseSettings("rollcall-test", "1:1:android:ab", "AIzaKey", "1")
    private val firebase = FirebaseSettingsStore(MemoryValues())
    private val endpoints = PushEndpointStore(MemoryValues())
    private val fcm = FakeFcm()
    private val events = mutableListOf<PushEndpointInfo?>()
    private var playServices = true
    private val route = FcmRoute(firebase, { playServices }, fcm, endpoints) { events += it }

    @Test
    fun isUsableOnlyWithFirebaseSetUpAndPlayServices() {
        assertFalse(route.usable())

        firebase.save(settings)
        assertTrue(route.usable())

        playServices = false
        assertFalse(route.usable())
    }

    @Test
    fun registeringKeepsAndPassesOnTheToken() {
        route.register("BVapid")

        val token = PushEndpointInfo.fcm("fcm-token:1")
        assertEquals(token, endpoints.load())
        assertEquals(listOf<PushEndpointInfo?>(token), events)
        assertEquals("fcm", route.route)
    }

    @Test
    fun aRefreshedTokenIsPassedOnWhileFcmIsTheRouteInUse() {
        route.register("BVapid")

        route.tokenRefreshed("fcm-token:2")

        assertEquals(PushEndpointInfo.fcm("fcm-token:2"), endpoints.load())
        assertEquals(PushEndpointInfo.fcm("fcm-token:2"), events.last())
    }

    @Test
    fun aRefreshedTokenIsIgnoredWhileADistributorIsInUse() {
        val distributor = PushEndpointInfo("https://ntfy.example.com/upAbc", "BKey", "auth")
        endpoints.save(distributor)

        route.tokenRefreshed("fcm-token:2")

        assertEquals(distributor, endpoints.load())
        assertEquals(emptyList<PushEndpointInfo?>(), events)
    }

    @Test
    fun unregisteringDeletesTheTokenAndForgetsIt() {
        route.register("BVapid")

        route.unregister()

        assertEquals(1, fcm.deleted)
        assertNull(endpoints.load())
    }

    @Test
    fun unregisteringKeepsADistributorsEndpoint() {
        val distributor = PushEndpointInfo("https://ntfy.example.com/upAbc", "BKey", "auth")
        endpoints.save(distributor)

        route.unregister()

        assertEquals(distributor, endpoints.load())
    }
}
