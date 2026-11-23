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
)
