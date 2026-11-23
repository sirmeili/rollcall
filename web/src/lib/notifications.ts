import type { NotificationKind } from "#lib/api/types.ts";

/** How the Account page names each kind of notification and says when it is sent. Which kinds
 * a user sees, and in what order, comes from the server (`Me.notifications`). */
export const NOTIFICATION_KINDS: Record<NotificationKind, { label: string; when: string }> = {
  new_request: { label: "New request", when: "A print request is submitted." },
  request_update: {
    label: "Request update",
    when: "Your request is approved, rejected, waiting on filament, printing, done, failed or cancelled.",
  },
  new_photo: { label: "New photo", when: "A photo of your print is added after it's done." },
  low_stock: { label: "Low stock", when: "A product becomes low stock." },
  suggestion: {
    label: "Suggestion",
    when: "Someone suggests a product or catalog color for the shopping list.",
  },
  nearly_out: { label: "Nearly out", when: "A spool in an AMS reaches its nearly-out cutoff." },
  backup_failed: { label: "Backup failed", when: "A nightly backup fails." },
};

/** "a print request is submitted", for "You'll be emailed when …". */
export function whenSentence(kind: NotificationKind): string {
  const when = NOTIFICATION_KINDS[kind].when.replace(/\.$/, "");
  return when.charAt(0).toLowerCase() + when.slice(1);
}
