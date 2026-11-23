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
    /** The four values, in the order of [NAMES]. */
    fun values(): List<String> = listOf(projectId, appId, apiKey, senderId)

    companion object {
        /** Each setting's name, as the server's push configuration names it. */
        val NAMES = listOf("project_id", "app_id", "api_key", "sender_id")

        /** The settings read by name with [value]; null unless all four are there. */
        fun read(value: (String) -> String?): FirebaseSettings? {
            val (projectId, appId, apiKey, senderId) = NAMES.map { value(it) ?: return null }
            return FirebaseSettings(projectId, appId, apiKey, senderId)
        }
    }
}
