package io.github.sirmeili.filamenttracker.push

/** One way this phone can get phone notifications, named for the web app by [route]. */
interface PushProvider {
    val route: String

    /** Whether this route works on this phone now, such as a distributor being installed. */
    fun usable(): Boolean

    /** The name people know this route by, such as the distributor app's ("ntfy"); null
     * when it can't be told. */
    fun displayName(): String?

    /** Register for pushes signed with the server's VAPID public key. The endpoint arrives
     * later, through [PushEvents]. */
    fun register(vapidKey: String)

    fun unregister()
}

/**
 * The push-provider choice: the first usable route, in order of preference: a UnifiedPush
 * distributor, if one is installed, then (in the google flavor) Google's push service when the
 * server has Firebase set up; otherwise there is none.
 */
class PushRoutes(private val providers: List<PushProvider>) {
    private fun chosen(): PushProvider? = providers.firstOrNull { it.usable() }

    /** The route in use, or [NONE]. */
    fun route(): String = chosen()?.route ?: NONE

    /** The name people know the route in use by, or null with none. */
    fun routeName(): String? = chosen()?.displayName()

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

        /** Google's push service (FCM), in the google flavor only. */
        const val FCM = "fcm"
    }
}
