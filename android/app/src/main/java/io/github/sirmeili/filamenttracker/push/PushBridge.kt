package io.github.sirmeili.filamenttracker.push

import android.content.Context
import android.content.Intent
import com.getcapacitor.JSObject
import io.github.sirmeili.filamenttracker.flavor.appFlavor

/**
 * The plugin's phone notification calls, in the shapes the web app reads: the route in use and
 * its name, registering and unregistering, the endpoint and its changes, and the server's
 * Firebase settings. Android's permission and tapped notifications stay in the plugin, which
 * they need.
 */
class PushBridge(private val context: Context) {
    private val endpoints by lazy { pushEndpoints(context) }
    private val routes by lazy { appFlavor.pushRoutes(context, endpoints) }

    fun route(): JSObject = JSObject().put("route", routes.route())

    /** The name people know the route by: the distributor app's ("ntfy"), or "Google". */
    fun routeName(): JSObject = JSObject().put("name", routes.routeName())

    fun register(vapidKey: String) = routes.register(vapidKey)

    fun unregister() = routes.unregister()

    fun endpoint(): JSObject = endpointJs(endpoints.load())

    /** Pass each new endpoint the route gives to [changed]; null stops. */
    fun listen(changed: ((JSObject) -> Unit)?) =
        PushEvents.listen(changed?.let { tell -> { endpoint -> tell(endpointJs(endpoint)) } })

    /**
     * Use the server's Firebase client settings (null: none), before choosing a route. True
     * when they differ from the ones Firebase is running with, so the app must [restart].
     */
    fun configure(firebase: JSObject?): Boolean {
        val settings = firebase?.let { json -> FirebaseSettings.fromServer { json.getString(it) } }
        return appFlavor.useFirebase(context, settings)
    }

    /** Start the app afresh in a new process, as Firebase starts once per process. */
    fun restart() {
        val launch = context.packageManager.getLaunchIntentForPackage(context.packageName) ?: return
        context.startActivity(Intent.makeRestartActivityTask(launch.component))
        Runtime.getRuntime().exit(0)
    }

    private fun endpointJs(endpoint: PushEndpointInfo?): JSObject =
        JSObject().put(
            "endpoint",
            endpoint?.let {
                JSObject().put("route", it.route).put("url", it.url).put("p256dh", it.p256dh).put("auth", it.auth)
            },
        )
}
