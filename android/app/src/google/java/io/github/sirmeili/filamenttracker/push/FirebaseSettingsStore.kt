package io.github.sirmeili.filamenttracker.push

import io.github.sirmeili.filamenttracker.storage.KeyValues

/** The server's Firebase client settings, kept so Firebase starts from them at the next app
 * start, even when the app is started for a notification. */
class FirebaseSettingsStore(private val values: KeyValues) {
    fun load(): FirebaseSettings? = FirebaseSettings.read(values::get)

    /** Keep these settings, or forget them (null). */
    fun save(settings: FirebaseSettings?) {
        if (settings == null) return FirebaseSettings.NAMES.forEach(values::remove)
        FirebaseSettings.NAMES.zip(settings.values()).forEach { (name, value) -> values.put(name, value) }
    }
}
