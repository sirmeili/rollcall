package io.github.sirmeili.filamenttracker.push

/** An Android notification channel: one per kind, so each can be muted in Android's settings.
 * Not a channel in the glossary's sense (email or phone). */
data class AndroidChannel(val id: String, val name: String)

/**
 * The channel for each kind of phone notification. The kinds are the server's
 * (server/src/filament_tracker/notifications/kinds.py), plus the test notification. A kind the
 * app doesn't know yet shows under [OTHER] until it gets its own channel here.
 */
object NotificationChannels {
    val OTHER = AndroidChannel("other", "Other notifications")

    private val KINDS =
        listOf(
            AndroidChannel("new_request", "New requests"),
            AndroidChannel("request_update", "Request updates"),
            AndroidChannel("new_photo", "New photos"),
            AndroidChannel("low_stock", "Low stock"),
            AndroidChannel("suggestion", "Suggestions"),
            AndroidChannel("nearly_out", "Nearly out"),
            AndroidChannel("backup_failed", "Backup failed"),
            AndroidChannel("test", "Test notifications"),
        )

    /** Every channel, to create when the app shows its first notification. */
    val ALL: List<AndroidChannel> = KINDS + OTHER

    fun of(kind: String): AndroidChannel = KINDS.firstOrNull { it.id == kind } ?: OTHER
}
