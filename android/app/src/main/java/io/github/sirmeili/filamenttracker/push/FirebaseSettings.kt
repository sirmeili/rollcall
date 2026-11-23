package io.github.sirmeili.filamenttracker.push

/**
 * The Firebase client settings the server hands a user's phone when it sends phone
 * notifications through Google's push service (FCM). Only the `google` flavor uses them; none
 * of them is secret. Plain data: no Firebase code.
 */
data class FirebaseSettings(
    val projectId: String,
    val appId: String,
    val apiKey: String,
    val senderId: String,
) {
    companion object {
        /** The settings as the server's push configuration names them, read with [value];
         * null unless all four are there. */
        fun fromServer(value: (String) -> String?): FirebaseSettings? {
            val values = listOf("project_id", "app_id", "api_key", "sender_id").map { value(it) ?: return null }
            return FirebaseSettings(values[0], values[1], values[2], values[3])
        }
    }
}
