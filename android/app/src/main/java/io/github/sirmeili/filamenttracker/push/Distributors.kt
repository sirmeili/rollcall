package io.github.sirmeili.filamenttracker.push

/** Which installed UnifiedPush distributor (an app such as ntfy) this phone uses. */
object Distributors {
    /**
     * The one in use while it is still installed; otherwise the phone's default distributor;
     * otherwise the first installed; null when none is installed.
     */
    fun choose(current: String?, default: String?, installed: List<String>): String? =
        current?.takeIf { it in installed }
            ?: default?.takeIf { it in installed }
            ?: installed.firstOrNull()
}
