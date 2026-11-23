/** What a Back press does in the phone app: one decision, shared by every page.
 *
 * In order: nothing while the start screen shows; close the top layer if one is open; back
 * one page if there is history before the current page; otherwise the app goes to the
 * background (it keeps running, so the page, a Delivery and queued scans are there when it
 * comes back).
 *
 * A layer is something open on top of a page: a sheet or a dialog. It registers with
 * `openLayer` while it is open, and Back closes only the most recently opened one.
 *
 * Going back a page is the browser's own `history.back()`, so it is the same navigation as
 * a browser's Back button.
 */

import { bridge, type BackPress } from "#lib/phone/bridge.ts";

export type BackAction = "nothing" | "layer" | "page" | "background";

/** The state of the app that a Back press depends on, read when Back is pressed. */
export interface BackContext {
  /** Whether the start screen is showing. */
  starting: boolean;
  /** Whether a layer is open. */
  layerOpen: boolean;
}

export function backAction(press: BackPress, context: BackContext): BackAction {
  if (context.starting) return "nothing";
  if (context.layerOpen) return "layer";
  if (press.canGoBack) return "page";
  return "background";
}

/** The open layers, oldest first. Each is a box so the same close can be open twice. */
const layers = new Set<{ close: () => void }>();

/** Register a layer as open, with how to close it, until the returned function is called.
 *
 * Back calls `close` on the top layer and nothing else: the layer stays registered until it
 * unregisters, so a close that keeps the layer open (or opens another on top) is fine. */
export function openLayer(close: () => void): () => void {
  const layer = { close };
  layers.add(layer);
  return () => void layers.delete(layer);
}

/** Handle every Back press the phone bridge reports, until the returned function is called.
 * `starting` (whether the start screen is showing) is read at each press. */
export function listenForBack(starting: () => boolean): () => void {
  const phoneBridge = bridge();
  return phoneBridge.onBack((press) => {
    const action = backAction(press, { starting: starting(), layerOpen: layers.size > 0 });
    if (action === "layer") [...layers].at(-1)!.close();
    else if (action === "page") history.back();
    else if (action === "background") void phoneBridge.background();
  });
}
