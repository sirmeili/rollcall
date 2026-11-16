/** Calls for the catalog: a local copy of the Open Filament Database's Bambu Lab colors.
 * Anyone signed in reads it; the sync status and Refresh now are Admin only. */

import { api } from "#lib/api/client.ts";

export type SyncResult = "updated" | "not_modified" | "failed";

export interface SyncStatus {
  last_success_at: string | null;
  last_attempt_at: string | null;
  last_result: SyncResult | null;
  /** Why the last attempt failed, when it did. */
  last_reason: string | null;
  dataset_version: string | null;
  /** Catalog colors in the copy in use. */
  colors: number;
}

export interface CatalogColor {
  uuid: string;
  name: string;
  /** RRGGBB, the main color first; more than one for a multi-color catalog color. */
  hexes: string[];
  discontinued: boolean;
  multi_color: boolean;
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
