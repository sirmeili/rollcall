/** The controls Tab moves between inside a dialog. */
const FOCUSABLE =
  "input:not(:disabled), select:not(:disabled), textarea:not(:disabled), button:not(:disabled)";

/** Keep Tab inside `box`: from its last control back to its first, and Shift+Tab the other
 * way. Call it from the dialog's keydown handler; other keys are left alone. */
export function keepTabInside(box: HTMLElement, event: KeyboardEvent): void {
  if (event.key !== "Tab") return;
  const all = [...box.querySelectorAll<HTMLElement>(FOCUSABLE)];
  const first = all[0];
  const last = all[all.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}
