package io.github.sirmeili.filamenttracker.push

/**
 * One phone notification, as the server's payload carries it: its kind, title, text, the
 * path of the page it opens and, for Done and New photo, the server path of the photo to show
 * (server/README.md, Phone notifications).
 */
data class PhoneNotification(
    val kind: String,
    val title: String,
    val text: String,
    val path: String,
    val photo: String? = null,
) {
    companion object {
        /** The notification from the payload's fields, or null without a title. */
        fun of(field: (String) -> String?): PhoneNotification? {
            val title = field("title")?.takeIf { it.isNotEmpty() } ?: return null
            return PhoneNotification(
                kind = field("kind").orEmpty(),
                title = title,
                text = field("text").orEmpty(),
                path = safePath(field("path")),
                photo = field("photo")?.takeIf(::onThisServer),
            )
        }

        /** A path on this app's server, or "/": a tapped notification never opens another
         * site. The web app checks it again before opening it. */
        fun safePath(path: String?): String = path?.takeIf(::onThisServer) ?: "/"

        private fun onThisServer(path: String): Boolean =
            path.startsWith("/") && !path.startsWith("//") && !path.startsWith("/\\")
    }
}
