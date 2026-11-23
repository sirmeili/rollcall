/** Android 13's permission to show notifications, asked once on a user's phone.
 *
 * It is asked after signing in on a new phone, and on the first open after the update that
 * brought phone notifications for a phone already set up (or as soon as the server first
 * says it is a user's phone). Whether it was asked is kept on the phone, and survives
 * Unlink, so it is never asked twice. Refusing it changes no setting: the Phone switches on
 * Account stay as they are, and Pairing says how to allow it.
 */

import type { PhoneBridge } from "#lib/phone/bridge.ts";

const ASKED_KEY = "notification_permission_asked";

/** Ask for the permission, unless it was asked before or is already granted. */
export async function askPermissionOnce(native: PhoneBridge): Promise<void> {
  if ((await native.secureGet(ASKED_KEY)) === "true") return;
  await native.secureSet(ASKED_KEY, "true");
  if ((await native.pushPermission()) === "granted") return;
  await native.requestPushPermission();
}
