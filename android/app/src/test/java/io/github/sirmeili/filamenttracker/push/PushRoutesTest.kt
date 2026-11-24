package io.github.sirmeili.filamenttracker.push

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PushRoutesTest {
    /** A route that is usable or not, recording what it was asked. */
    private class FakeProvider(override val route: String, var usable: Boolean) : PushProvider {
        val registrations = mutableListOf<String>()
        var unregistrations = 0

        override fun usable() = usable

        override fun displayName() = "$route app"

        override fun register(vapidKey: String) {
            registrations += vapidKey
        }

        override fun unregister() {
            unregistrations += 1
        }
    }

    @Test
    fun usesUnifiedPushWhenADistributorIsInstalled() {
        val unifiedPush = FakeProvider("unifiedpush", usable = true)
        val routes = PushRoutes(listOf(unifiedPush))

        assertEquals("unifiedpush", routes.route())
        assertTrue(routes.register("BVapid"))
        assertEquals(listOf("BVapid"), unifiedPush.registrations)
    }

    @Test
    fun hasNoRouteWithoutADistributor() {
        val unifiedPush = FakeProvider("unifiedpush", usable = false)
        val routes = PushRoutes(listOf(unifiedPush))

        assertEquals("none", routes.route())
        assertFalse(routes.register("BVapid"))
        assertEquals(emptyList<String>(), unifiedPush.registrations)
    }

    @Test
    fun hasNoRouteWithNoProviders() {
        assertEquals("none", PushRoutes(emptyList()).route())
    }

    @Test
    fun prefersTheFirstUsableRoute() {
        val first = FakeProvider("unifiedpush", usable = false)
        val second = FakeProvider("other", usable = true)
        val routes = PushRoutes(listOf(first, second))

        assertEquals("other", routes.route())
        first.usable = true
        assertEquals("unifiedpush", routes.route())
        routes.register("BVapid")
        assertEquals(listOf("BVapid"), first.registrations)
        assertEquals(emptyList<String>(), second.registrations)
    }

    @Test
    fun namesTheChosenRouteByItsOwnName() {
        val first = FakeProvider("unifiedpush", usable = false)
        val second = FakeProvider("other", usable = true)
        val routes = PushRoutes(listOf(first, second))

        assertEquals("other app", routes.routeName())
        second.usable = false
        assertNull(routes.routeName())
    }

    @Test
    fun unregistersFromEveryRoute() {
        // The route in use may have changed since registering (a distributor removed), so
        // unregistering asks each one.
        val first = FakeProvider("unifiedpush", usable = true)
        val second = FakeProvider("other", usable = false)

        PushRoutes(listOf(first, second)).unregister()

        assertEquals(1, first.unregistrations)
        assertEquals(1, second.unregistrations)
    }
}
