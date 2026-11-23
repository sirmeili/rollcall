/** Unsaved changes, and the warning before leaving them: one piece that every form shares.
 *
 * A form has unsaved changes when one of its fields (an input, textarea or select inside a
 * `<form>`) differs from what it was when the person started on it. It's worked out from the
 * fields themselves, so a new form needs no wiring. Each field's first value is taken the
 * first time the person reaches into its form (a tap, a key or focus), before they can change
 * anything, so values a page fills in as it loads count as the start. A field changed back
 * counts as unchanged.
 *
 * A save resets the comparison. An API write the server accepts saves the form the person
 * last acted in (tapped, typed in or submitted) when the write started, whatever button made
 * it: that form's first values are forgotten, and taken again the next time the person
 * reaches into it, from what the page shows by then (the saved values, as the server sent
 * them back). A write the server refuses leaves the changes unsaved.
 *
 * `askToLeave` shows the warning (`LeaveWarning.svelte`, in the layout) when there are unsaved
 * changes, and says whether the person chose Leave.
 */

import { onWrite } from "#lib/api/client.ts";

type Field = HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;

const FIELDS = "form input, form textarea, form select";

/** Each field's value when it started, by field. A field not in it hasn't been reached. */
let started = new WeakMap<Field, string>();

/** The form the person last acted in, or null after acting outside every form. */
let acting: HTMLFormElement | null = null;

function fieldsIn(root: ParentNode): Field[] {
  return [...root.querySelectorAll<Field>(FIELDS)];
}

/** A field's value, comparable with its first one. */
function valueOf(field: Field): string {
  if (field instanceof HTMLSelectElement)
    return [...field.selectedOptions].map((option) => option.value).join("\n");
  if (field instanceof HTMLInputElement && (field.type === "checkbox" || field.type === "radio"))
    return String(field.checked);
  return field.value;
}

/** Whether a form inside `within` (the whole page unless given) has unsaved changes. */
export function hasUnsavedChanges(within: ParentNode = document): boolean {
  return fieldsIn(within).some(
    (field) => started.has(field) && started.get(field) !== valueOf(field),
  );
}

/** Forget every form's first values: the page they belonged to is being left. */
export function forgetChanges(): void {
  started = new WeakMap();
}

function formOf(event: Event): HTMLFormElement | null {
  return (event.target as Element).closest?.("form") ?? null;
}

function reached(event: Event): void {
  const form = formOf(event);
  if (!form) return;
  for (const field of fieldsIn(form)) if (!started.has(field)) started.set(field, valueOf(field));
}

function acted(event: Event): void {
  acting = formOf(event);
}

/** A write is starting: if the server accepts it, the form the person is acting in is saved. */
function writing(): () => void {
  const form = acting;
  return () => form && fieldsIn(form).forEach((field) => started.delete(field));
}

/** Watch the page's forms, until the returned function is called. */
export function watchForms(): () => void {
  const reach = ["pointerdown", "keydown", "focusin"] as const;
  const act = ["pointerdown", "keydown", "submit"] as const;
  reach.forEach((type) => document.addEventListener(type, reached, true));
  act.forEach((type) => document.addEventListener(type, acted, true));
  const unwrite = onWrite(writing);
  return () => {
    reach.forEach((type) => document.removeEventListener(type, reached, true));
    act.forEach((type) => document.removeEventListener(type, acted, true));
    unwrite();
    acting = null;
  };
}

/** The open warning's answer, or null while none shows. */
let answer = $state<((leave: boolean) => void) | null>(null);

/** The warning, as `LeaveWarning.svelte` shows it. */
export const leaveWarning = {
  get open(): boolean {
    return answer !== null;
  },
  /** Stay (false) or Leave (true). */
  answer(leave: boolean): void {
    const given = answer;
    answer = null;
    given?.(leave);
  },
};

/** Whether to go ahead with leaving forms inside `within` (the whole page unless given):
 * straight away without unsaved changes, otherwise once the person chooses Leave. While the
 * warning already shows, a second ask stays. */
export function askToLeave(within: ParentNode = document): Promise<boolean> {
  if (!hasUnsavedChanges(within)) return Promise.resolve(true);
  if (answer) return Promise.resolve(false);
  return new Promise((resolve) => (answer = resolve));
}
