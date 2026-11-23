package io.github.sirmeili.filamenttracker.push

import android.content.Context
import org.unifiedpush.android.connector.UnifiedPush
import org.unifiedpush.android.connector.data.ResolvedDistributor

/**
 * Phone notifications through a UnifiedPush distributor such as ntfy, with the UnifiedPush
 * connector library. The distributor gives an endpoint and Web Push keys to [UnifiedPushService],
 * and decrypts each push for it.
 */
class UnifiedPushProvider(private val context: Context, private val endpoints: PushEndpointStore) : PushProvider {
    override val route = ROUTE

    override fun usable() = UnifiedPush.getDistributors(context).isNotEmpty()

    override fun register(vapidKey: String) {
        val distributor = distributor() ?: return
        UnifiedPush.saveDistributor(context, distributor)
        UnifiedPush.register(context, INSTANCE, DISTRIBUTOR_MESSAGE, vapidKey)
    }

    override fun unregister() {
        UnifiedPush.unregister(context, INSTANCE)
        endpoints.clear()
    }

    /** The distributor app in use, or that would be, by its name on the phone ("ntfy"). */
    fun distributorName(): String? {
        val distributor = distributor() ?: return null
        val packages = context.packageManager
        return runCatching { packages.getApplicationLabel(packages.getApplicationInfo(distributor, 0)).toString() }
            .getOrNull()
    }

    private fun distributor(): String? {
        val default = (UnifiedPush.resolveDefaultDistributor(context) as? ResolvedDistributor.Found)?.packageName
        return Distributors.choose(UnifiedPush.getAckDistributor(context), default, UnifiedPush.getDistributors(context))
    }

    companion object {
        const val ROUTE = "unifiedpush"
        private const val INSTANCE = "default"

        // Shown by some distributors next to the registration.
        private const val DISTRIBUTOR_MESSAGE = "RollCall phone notifications"
    }
}
