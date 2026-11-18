/** Loads what the filament picker offers: the inventory and the catalog. Either can fail
 * on its own; the picker then offers what did load and says what didn't. */

import { getCatalog, type Catalog } from "#lib/api/catalog.ts";
import { describeError } from "#lib/api/errors.ts";
import { getInventory } from "#lib/api/stock.ts";
import type { ProductSummary } from "#lib/api/types.ts";
import { pickerOptions, type PickerOptions } from "#lib/requests/picker.ts";

export interface LoadedOptions {
  options: PickerOptions;
  failure: string | null;
}

export async function loadOptions(): Promise<LoadedOptions> {
  const [inventory, catalog] = await Promise.allSettled([getInventory(), getCatalog()]);
  const failed = [inventory, catalog].find((r) => r.status === "rejected");
  return {
    options: pickerOptions(
      inventory.status === "fulfilled" ? (inventory.value as ProductSummary[]) : [],
      catalog.status === "fulfilled" ? (catalog.value as Catalog) : null,
    ),
    failure: failed ? `Some filament couldn't be loaded: ${describeError(failed.reason)}` : null,
  };
}
