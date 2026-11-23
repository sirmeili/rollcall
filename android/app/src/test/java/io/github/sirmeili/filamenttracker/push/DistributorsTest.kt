package io.github.sirmeili.filamenttracker.push

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class DistributorsTest {
    private val ntfy = "io.heckel.ntfy"
    private val other = "org.example.distributor"

    @Test
    fun keepsTheDistributorInUseWhileItIsInstalled() {
        assertEquals(ntfy, Distributors.choose(current = ntfy, default = other, installed = listOf(other, ntfy)))
    }

    @Test
    fun otherwiseUsesThePhonesDefault() {
        assertEquals(other, Distributors.choose(current = null, default = other, installed = listOf(ntfy, other)))
        assertEquals(other, Distributors.choose(current = "gone", default = other, installed = listOf(ntfy, other)))
    }

    @Test
    fun otherwiseUsesTheFirstInstalled() {
        assertEquals(ntfy, Distributors.choose(current = null, default = null, installed = listOf(ntfy, other)))
        assertEquals(ntfy, Distributors.choose(current = null, default = "gone", installed = listOf(ntfy)))
    }

    @Test
    fun hasNoneWhenNoneIsInstalled() {
        assertNull(Distributors.choose(current = ntfy, default = ntfy, installed = emptyList()))
    }
}
