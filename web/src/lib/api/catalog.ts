/** Calls for the catalog: local copies of the Open Filament Database's Bambu Lab colors and
 * BambuStudio's color code list. Anyone signed in reads it; the sync status and Refresh now
 * are Admin only. */

import { api } from "#lib/api/client.ts";

export type SyncResult = "updated" | "not_modified" | "failed";

/** One source's syncs: OFDB's export or BambuStudio's color code list. */
export interface SourceStatus {
  last_success_at: string | null;
  last_attempt_at: string | null;
  last_result: SyncResult | null;
  /** Why the last attempt failed, when it did. */
  last_reason: string | null;
  /** OFDB's only; always null for BambuStudio's list. */
  dataset_version: string | null;
}

export interface SyncStatus {
  /** Catalog colors in the copy in use. */
  colors: number;
  ofdb: SourceStatus;
  bambustudio: SourceStatus;
}

/** An in-stock product whose color is close to a catalog color. */
export interface SimilarColor {
  product_id: number;
  name: string;
  /** RRGGBB */
  hex: string;
  material: string;
  delta_e: number;
  sealed: number;
  open: number;
  different_material: boolean;
}

/** How a product's catalog link was made: from its tag, or by hand. */
export type LinkHow = "tag" | "hand";

/** An in-stock product linked to a catalog color. */
export interface OwnedProduct {
  product_id: number;
  name: string;
  /** RRGGBB */
  hex: string;
  material: string;
  how: LinkHow;
  sealed: number;
  open: number;
}

/** A product linked to a catalog color, with no Sealed or Open spool. */
export interface LinkedProduct {
  product_id: number;
  name: string;
}

export interface CatalogColor {
  uuid: string;
  name: string;
  /** RRGGBB, the main color first; more than one for a multi-color catalog color. */
  hexes: string[];
  discontinued: boolean;
  multi_color: boolean;
  /** A multi-color one whose colors blend along the filament, not side by side. */
  gradient: boolean;
  /** The 5-digit number Bambu Lab sells it under; null when it has none. */
  bambu_code: string | null;
  /** In-stock products within the cutoff and not linked to it, closest first; empty for a
   * multi-color one. */
  similar: SimilarColor[];
  /** A product linked to it has a Sealed or Open spool. */
  owned: boolean;
  /** Its linked products with a Sealed or Open spool, by name. */
  owned_products: OwnedProduct[];
  /** Its linked products with none in stock, by name. */
  linked_none_in_stock: LinkedProduct[];
}

export interface FilamentLine {
  uuid: string;
  name: string;
  material: string;
  colors: CatalogColor[];
}

export interface Catalog {
  lines: FilamentLine[];
  /** Whether the catalog has ever been downloaded. */
  synced: boolean;
  dataset_version: string | null;
  last_success_at: string | null;
  /** The ΔE the similar in-stock colors were found with. */
  cutoff: number;
  /** Syncs have failed for 14 days since the last success. */
  out_of_date: boolean;
  /** The store Find in store searches, without a trailing slash. */
  store_address: string;
}

/** Every filament line with its catalog colors (Viewer and above). */
export function getCatalog(): Promise<Catalog> {
  return api<Catalog>("/catalog");
}

export function getSyncStatus(): Promise<SyncStatus> {
  return api<SyncStatus>("/catalog/sync");
}

/** Sync now and get the new status. A failed sync still answers; one already running is
 * refused (409) and nothing new starts. */
export function refreshCatalog(): Promise<SyncStatus> {
  return api<SyncStatus>("/catalog/sync", { method: "POST" });
}
