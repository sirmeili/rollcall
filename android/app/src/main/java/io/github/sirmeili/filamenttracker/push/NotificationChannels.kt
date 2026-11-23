package io.github.sirmeili.filamenttracker.push

/** An Android notification channel: one per kind, so each can be muted in Android's settings. */
data class Channel(val id: String, val name: String)

/**
 * The channel for each kind of phone notification. The kinds are the server's
 * (server/src/filament_tracker/notifications/kinds.py), plus the test notification. A kind the
 * app doesn't know yet shows under [OTHER] until it gets its own channel here.
 */
object NotificationChannels {
    val OTHER = Channel("other", "Other notifications")

    private val KINDS =
        listOf(
            Channel("new_request", "New requests"),
            Channel("request_update", "Request updates"),
            Channel("new_photo", "New photos"),
            Channel("low_stock", "Low stock"),
            Channel("suggestion", "Suggestions"),
            Channel("nearly_out", "Nearly out"),
            Channel("backup_failed", "Backup failed"),
            Channel("test", "Test notifications"),
        )

    /** Every channel, to create when the app shows its first notification. */
    val ALL: List<Channel> = KINDS + OTHER

    fun of(kind: String): Channel = KINDS.firstOrNull { it.id == kind } ?: OTHER
}
