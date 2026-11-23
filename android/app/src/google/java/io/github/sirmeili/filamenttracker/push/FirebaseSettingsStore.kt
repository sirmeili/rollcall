package io.github.sirmeili.filamenttracker.push

import io.github.sirmeili.filamenttracker.storage.KeyValues

/** The server's Firebase client settings, kept so Firebase starts from them at the next app
 * start, even when the app is started for a notification. */
class FirebaseSettingsStore(private val values: KeyValues) {
    fun load(): FirebaseSettings? {
        val (projectId, appId, apiKey, senderId) = NAMES.map { values.get(it) ?: return null }
        return FirebaseSettings(projectId, appId, apiKey, senderId)
    }

    /** Keep these settings, or forget them (null). */
    fun save(settings: FirebaseSettings?) {
        if (settings == null) return NAMES.forEach(values::remove)
        listOf(settings.projectId, settings.appId, settings.apiKey, settings.senderId)
            .zip(NAMES)
            .forEach { (value, name) -> values.put(name, value) }
    }

    private companion object {
        val NAMES = listOf("project_id", "app_id", "api_key", "sender_id")
    }
}
