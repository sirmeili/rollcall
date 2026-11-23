package io.github.sirmeili.filamenttracker.push

/** The `google` flavor's routes, in order of preference: an installed UnifiedPush distributor,
 * so a phone with ntfy keeps using it, then Google's push service (FCM). */
fun googleRoutes(unifiedPush: PushProvider, fcm: PushProvider) = PushRoutes(listOf(unifiedPush, fcm))
