package io.github.sirmeili.filamenttracker.push

/** One way this phone can get phone notifications, named for the web app by [route]. */
interface PushProvider {
    val route: String

    /** Whether this route works on this phone now, such as a distributor being installed. */
    fun usable(): Boolean

    /** Register for pushes signed with the server's VAPID public key. The endpoint arrives
     * later, through [PushEvents]. */
    fun register(vapidKey: String)

    fun unregister()
}

/**
 * The push-provider choice: the first usable route, in order of preference. For now the only
 * route is a UnifiedPush distributor, if one is installed; otherwise there is none.
 */
class PushRoutes(private val providers: List<PushProvider>) {
    private fun chosen(): PushProvider? = providers.firstOrNull { it.usable() }

    /** The route in use, or [NONE]. */
    fun route(): String = chosen()?.route ?: NONE

    /** Register with the chosen route; false when there is none. */
    fun register(vapidKey: String): Boolean {
        val provider = chosen() ?: return false
        provider.register(vapidKey)
        return true
    }

    /** Stop every route: the one registered with may no longer be the one chosen. */
    fun unregister() = providers.forEach { it.unregister() }

    companion object {
        const val NONE = "none"
    }
}
