/** Makes a component a layer for the phone's Back button while it is mounted. */

import { askToLeave } from "#lib/leave-warning.svelte.ts";
import { openLayer } from "#lib/phone/back.ts";

/** Call while a component initialises: from now until it unmounts, Back calls `close`
 * (unless a layer opened later is on top). `close` is read when Back is pressed, so pass
 * `() => onclose()` to follow a prop. */
export function backCloses(close: () => void): void {
  $effect(() => openLayer(close));
}

/** As `backCloses`, for a dialog holding a form: Back asks first when the form inside the
 * dialog (`dialog()`, read when Back is pressed) has unsaved changes, and closes it only on
 * Leave. */
export function backClosesAsking(dialog: () => ParentNode, close: () => void): void {
  backCloses(() => void askToLeave(dialog()).then((leave) => leave && close()));
}
