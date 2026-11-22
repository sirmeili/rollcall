/** Makes a component a layer for the phone's Back button while it is mounted. */

import { openLayer } from "#lib/phone/back.ts";

/** Call while a component initialises: from now until it unmounts, Back calls `close`
 * (unless a layer opened later is on top). `close` is read when Back is pressed, so pass
 * `() => onclose()` to follow a prop. */
export function backCloses(close: () => void): void {
  $effect(() => openLayer(close));
}
