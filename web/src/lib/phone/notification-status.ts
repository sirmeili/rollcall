/** Whether phone notifications work on this phone, and sending a test one, for the Phone
 * notifications line on Pairing. */

import { api } from "#lib/api/client.ts";
import { describeError } from "#lib/api/errors.ts";
import type { PhoneBridge, PushRoute } from "#lib/phone/bridge.ts";

/** Working, by the named route; Android's permission refused; or no route on this phone. */
export type PhoneNotificationStatus =
  { state: "working"; via: string } | { state: "refused" } | { state: "no_route" };

/** Each route's name, for when the phone gives none. */
const ROUTE_NAMES: Record<Exclude<PushRoute, "none">, string> = {
  unifiedpush: "UnifiedPush",
};

export async function phoneNotificationStatus(
  native: PhoneBridge,
): Promise<PhoneNotificationStatus> {
  const route = await native.pushRoute();
  if (route === "none") return { state: "no_route" };
  if ((await native.pushPermission()) !== "granted") return { state: "refused" };
  return { state: "working", via: (await native.pushRouteName()) || ROUTE_NAMES[route] };
}

/** What the server said about a test notification: sent, or why not. */
export interface TestResult {
  ok: boolean;
  message: string;
}

/** Ask the server to send a test phone notification to this phone. */
export async function sendTestNotification(
  deviceId: string,
  fetchFn?: typeof fetch,
): Promise<TestResult> {
  try {
    return await api<TestResult>(
      `/push/devices/${encodeURIComponent(deviceId)}/test`,
      { method: "POST" },
      fetchFn,
    );
  } catch (error) {
    return { ok: false, message: describeError(error) };
  }
}
