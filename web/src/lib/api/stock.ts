/** Calls behind the stock pages: inventory, products, spools and their events. */

import { api } from "#lib/api/client.ts";
import type {
  ActionResult,
  ManualAction,
  Page,
  Product,
  ProductSummary,
  ReviewOut,
  SpoolDetail,
  SpoolRow,
  SpoolState,
} from "#lib/api/types.ts";

export function getInventory(): Promise<ProductSummary[]> {
  return api<ProductSummary[]>("/inventory");
}

export interface SpoolQuery {
  states?: SpoolState[];
  type?: string;
  q?: string;
  limit?: number;
  offset?: number;
}

/** The query string for `GET /spools`, leaving out empty filters. */
export function spoolQuery(query: SpoolQuery): string {
  const params = new URLSearchParams();
  for (const state of query.states ?? []) params.append("state", state);
  if (query.type) params.set("type", query.type);
  if (query.q?.trim()) params.set("q", query.q.trim());
  if (query.limit !== undefined) params.set("limit", String(query.limit));
  if (query.offset) params.set("offset", String(query.offset));
  const text = params.toString();
  return text ? `?${text}` : "";
}

export function listSpools(query: SpoolQuery, signal?: AbortSignal): Promise<Page<SpoolRow>> {
  return api<Page<SpoolRow>>(`/spools${spoolQuery(query)}`, { signal });
}

export function getSpool(id: number): Promise<SpoolDetail> {
  return api<SpoolDetail>(`/spools/${id}`);
}

/** A spool edit: only the fields sent change. Net weight and grams left are for Admins. */
export interface SpoolChanges {
  location?: string | null;
  notes?: string | null;
  net_weight_g?: number | null;
  grams_left_g?: number;
}

export function updateSpool(id: number, changes: SpoolChanges): Promise<SpoolDetail> {
  return api<SpoolDetail>(`/spools/${id}`, { method: "PATCH", body: changes });
}

export function moveSpools(spoolIds: number[], location: string | null): Promise<SpoolRow[]> {
  return api<SpoolRow[]>("/spools", {
    method: "PATCH",
    body: { spool_ids: spoolIds, location },
  });
}

export function recordAction(id: number, action: ManualAction): Promise<ActionResult> {
  return api<ActionResult>(`/spools/${id}/events`, { method: "POST", body: { action } });
}

export function undoEvent(eventId: string): Promise<unknown> {
  return api(`/events/${eventId}/revert`, { method: "POST" });
}

export type ProductChanges = Partial<
  Pick<Product, "display_name" | "low_stock_threshold" | "nearly_out_pct">
> & {
  /** A catalog color's UUID links the product by hand; null clears the manual link. */
  catalog_color?: string | null;
};

export function updateProduct(id: number, changes: ProductChanges): Promise<Product> {
  return api<Product>(`/products/${id}`, { method: "PATCH", body: changes });
}

/** How many items a Review answer holds. */
export function waitingIn(review: ReviewOut): number {
  return (
    review.flagged_events.length +
    review.unidentified_tags.length +
    review.likely_empty.length +
    review.possible_duplicates.length
  );
}

/** How many items are waiting in Review, for the badge in the header. */
export async function reviewCount(): Promise<number> {
  const review = await api<ReviewOut>("/review");
  return waitingIn(review);
}
