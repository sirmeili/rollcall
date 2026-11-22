/** What a Back press does in the phone app: one decision, shared by every page.
 *
 * In order: nothing while the start screen shows; back one page if there is history before
 * the current page; otherwise the app goes to the background (it keeps running, so the page,
 * a Delivery and queued scans are there when it comes back). Closing an open layer (a sheet,
 * a dialog, the scan card) comes before going back a page, once layers register.
 *
 * Going back a page is the browser's own `history.back()`, so it is the same navigation as
 * a browser's Back button.
 */

import { bridge, type BackPress } from "#lib/phone/bridge.ts";

export type BackAction = "nothing" | "page" | "background";

/** The state of the app that a Back press depends on, read when Back is pressed. */
export interface BackContext {
  /** Whether the start screen is showing. */
  starting: boolean;
}

export function backAction(press: BackPress, context: BackContext): BackAction {
  if (context.starting) return "nothing";
  if (press.canGoBack) return "page";
  return "background";
}

/** Handle every Back press the phone bridge reports, until the returned function is called.
 * `context` is read at each press. */
export function listenForBack(context: () => BackContext): () => void {
  const phoneBridge = bridge();
  return phoneBridge.onBack((press) => {
    const action = backAction(press, context());
    if (action === "page") history.back();
    else if (action === "background") void phoneBridge.background();
  });
}
