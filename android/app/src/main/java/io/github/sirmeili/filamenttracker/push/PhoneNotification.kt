package io.github.sirmeili.filamenttracker.push

/**
 * One phone notification, as the server's payload carries it: its kind, title, text and the
 * path of the page it opens (server/README.md, Phone notifications).
 */
data class PhoneNotification(val kind: String, val title: String, val text: String, val path: String) {
    companion object {
        /** The notification from the payload's fields, or null without a title. */
        fun of(field: (String) -> String?): PhoneNotification? {
            val title = field("title")?.takeIf { it.isNotEmpty() } ?: return null
            return PhoneNotification(
                kind = field("kind").orEmpty(),
                title = title,
                text = field("text").orEmpty(),
                path = safePath(field("path")),
            )
        }

        /** A path on this app's server, or "/": a tapped notification never opens another
         * site. The web app checks it again before opening it. */
        fun safePath(path: String?): String =
            path?.takeIf { it.startsWith("/") && !it.startsWith("//") && !it.startsWith("/\\") } ?: "/"
    }
}
