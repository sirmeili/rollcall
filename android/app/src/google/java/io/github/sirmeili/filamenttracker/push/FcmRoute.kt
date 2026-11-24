package io.github.sirmeili.filamenttracker.push

/** Firebase Cloud Messaging's token calls, behind an interface so the route can be tested
 * without Firebase. */
interface FcmClient {
    /** Ask FCM for this phone's registration token; [onToken] gets it when it comes. */
    fun token(onToken: (String) -> Unit)

    fun deleteToken()
}

/**
 * Phone notifications through Google's push service (FCM), in the `google` flavor. Usable when
 * the server has Firebase set up (its settings are kept) and Google Play services are on the
 * phone. The FCM registration token is this phone's endpoint, sent to the server with the route
 * `fcm`. The server's VAPID key isn't used: FCM authenticates the server itself.
 */
class FcmRoute(
    private val firebase: FirebaseSettingsStore,
    private val playServices: () -> Boolean,
    private val fcm: FcmClient,
    private val endpoints: PushEndpointStore,
    private val changed: (PushEndpoint?) -> Unit = PushEvents::endpointChanged,
) : PushProvider {
    override val route = ROUTE

    override fun usable() = firebase.load() != null && playServices()

    override fun displayName() = NAME

    override fun register(vapidKey: String) = fcm.token(::given)

    override fun unregister() {
        fcm.deleteToken()
        if (inUse()) endpoints.clear()
    }

    /** FCM gave a new token, perhaps while the app was closed. It is kept and passed on only
     * while FCM is the route in use, so it never replaces a distributor's endpoint. */
    fun tokenRefreshed(token: String) {
        if (inUse()) given(token)
    }

    private fun inUse() = endpoints.load()?.route == PushEndpoint.FCM

    private fun given(token: String) {
        val endpoint = PushEndpoint.fcm(token)
        endpoints.save(endpoint)
        changed(endpoint)
    }

    companion object {
        /** What the web app shows as "via Google". */
        const val ROUTE = PushRoutes.FCM

        /** What people know Google's push service by. */
        const val NAME = "Google"
    }
}
