package io.github.sirmeili.filamenttracker.push

/**
 * Endpoint changes from the push service to the open app. The service runs even while the app
 * is closed; then nobody listens and the change is only stored, for the app to read when it
 * next registers.
 */
object PushEvents {
    @Volatile private var listener: ((PushEndpoint?) -> Unit)? = null

    /** Follow endpoint changes, or stop (null). One listener: the open app's plugin. */
    fun listen(next: ((PushEndpoint?) -> Unit)?) {
        listener = next
    }

    /** The route gave a new endpoint, or dropped this phone (null). */
    fun endpointChanged(endpoint: PushEndpoint?) {
        listener?.invoke(endpoint)
    }
}
