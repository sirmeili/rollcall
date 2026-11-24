package io.github.sirmeili.filamenttracker.push

/**
 * What to do when the server's Firebase settings arrive. Firebase is started once per app
 * start, so settings that differ from the running ones (changed on the server, removed, or
 * another server paired with) take effect only after the app restarts.
 */
enum class FirebaseStartup {
    NOTHING,
    START,
    RESTART,
    ;

    companion object {
        fun decide(running: FirebaseSettings?, wanted: FirebaseSettings?): FirebaseStartup =
            when {
                running == wanted -> NOTHING
                running == null -> START
                else -> RESTART
            }
    }
}
