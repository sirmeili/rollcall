package io.github.sirmeili.filamenttracker.push

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** The google flavor's choice of route: a UnifiedPush distributor, else FCM when the server
 * has Firebase set up, else none. */
class GoogleRoutesTest {
    private class FakeProvider(override val route: String, var usable: Boolean) : PushProvider {
        val registrations = mutableListOf<String>()

        override fun usable() = usable

        override fun displayName() = route

        override fun register(vapidKey: String) {
            registrations += vapidKey
        }

        override fun unregister() = Unit
    }

    private val unifiedPush = FakeProvider("unifiedpush", usable = false)
    private val fcm = FakeProvider("fcm", usable = false)
    private val routes = googleRoutes(unifiedPush, fcm)

    @Test
    fun aDistributorIsPreferredOverFcm() {
        unifiedPush.usable = true
        fcm.usable = true

        assertEquals("unifiedpush", routes.route())
        assertTrue(routes.register("BVapid"))
        assertEquals(listOf("BVapid"), unifiedPush.registrations)
        assertEquals(emptyList<String>(), fcm.registrations)
    }

    @Test
    fun withoutADistributorFcmIsUsedWhenSetUp() {
        fcm.usable = true

        assertEquals("fcm", routes.route())
        assertTrue(routes.register("BVapid"))
        assertEquals(listOf("BVapid"), fcm.registrations)
    }

    @Test
    fun withNeitherThereIsNoRoute() {
        assertEquals("none", routes.route())
        assertFalse(routes.register("BVapid"))
    }
}
