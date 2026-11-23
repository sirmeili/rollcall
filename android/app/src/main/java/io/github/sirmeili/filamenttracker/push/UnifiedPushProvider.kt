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
        val default = (UnifiedPush.resolveDefaultDistributor(context) as? ResolvedDistributor.Found)?.packageName
        val distributor =
            Distributors.choose(UnifiedPush.getAckDistributor(context), default, UnifiedPush.getDistributors(context))
                ?: return
        UnifiedPush.saveDistributor(context, distributor)
        UnifiedPush.register(context, INSTANCE, DISTRIBUTOR_MESSAGE, vapidKey)
    }

    override fun unregister() {
        UnifiedPush.unregister(context, INSTANCE)
        endpoints.clear()
    }

    companion object {
        const val ROUTE = "unifiedpush"
        private const val INSTANCE = "default"

        // Shown by some distributors next to the registration.
        private const val DISTRIBUTOR_MESSAGE = "RollCall phone notifications"
    }
}
