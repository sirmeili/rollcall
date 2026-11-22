import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { setTimeZone } from "#lib/format.ts";
import {
  findInStore,
  historyText,
  historyWhen,
  reasonText,
  shoppingGroups,
  sizeProblem,
  sizeText,
  spoolsText,
} from "#lib/shopping-list.ts";
import { product } from "../test/fixtures.ts";
import {
  added,
  handReason,
  link,
  lowItem,
  requestReason,
  STORE,
  shoppingList,
} from "../test/shopping-fixtures.ts";

describe("spoolsText", () => {
  it("counts spools", () => {
    expect(spoolsText(1)).toBe("1 spool");
    expect(spoolsText(3)).toBe("3 spools");
  });
});

describe("reasonText", () => {
  it("says why a low-stock product is on the list", () => {
    expect(reasonText({ kind: "low_stock", spools: 2, sealed: 1, threshold: 2 })).toBe(
      "Low stock: 1 sealed, threshold 2 · 2 spools",
    );
    expect(reasonText({ kind: "low_stock", spools: 1, sealed: 0, threshold: 0 + 0 })).toBe(
      "Low stock: 0 sealed, threshold 0 · 1 spool",
    );
  });
});

describe("reasonText for spools added by hand", () => {
  it("says who added them", () => {
    expect(reasonText(handReason(1, 2))).toBe("Added by hand by frank · 2 spools");
    expect(reasonText(handReason(1, 1, null))).toBe("Added by hand · 1 spool");
  });
});

describe("reasonText for print requests", () => {
  it("names a request the viewer may see, and its grams short", () => {
    expect(reasonText(requestReason(4, 300))).toBe("Lamp shade · 300 g short");
  });

  it("reads as a print request otherwise", () => {
    expect(reasonText(requestReason(null, 250))).toBe("A print request · 250 g short");
  });
});

describe("an item's size", () => {
  it("says the size and where it came from", () => {
    expect(sizeText({ grams: 3000, source: "chosen" })).toBe("3000 g spools (chosen)");
    expect(sizeText({ grams: 750, source: "last_spool" })).toBe(
      "750 g spools (from the last spool received)",
    );
    expect(sizeText({ grams: 1000, source: "catalog" })).toBe("1000 g spools (from the catalog)");
    expect(sizeText({ grams: 1000, source: "default" })).toBe("1000 g spools (the default)");
  });

  it("takes a whole number of grams from 1 to 10,000", () => {
    expect(sizeProblem(1)).toBeNull();
    expect(sizeProblem(10_000)).toBeNull();
    for (const bad of [null, 0, 10_001, 2.5]) {
      expect(sizeProblem(bad)).toBe("Size: a whole number of grams, 1 to 10,000.");
    }
  });
});

describe("the shopping list history", () => {
  beforeEach(() => setTimeZone("UTC"));
  afterEach(() => setTimeZone(undefined));

  it("says what was done", () => {
    expect(historyText(added(2))).toBe("Added 2 spools by hand");
    expect(historyText({ ...added(1), action: "removed_by_hand" })).toBe(
      "Removed 1 spool added by hand",
    );
    expect(historyText({ ...added(1), action: "brought_back" })).toBe("Brought back");
    expect(historyText({ ...added(1), action: "size_changed", spools: null, size_g: 3000 })).toBe(
      "Size set to 3000 g",
    );
  });

  it("tells a second order from a correction of on order", () => {
    expect(historyText({ ...added(2), action: "ordered", on_order: 3 })).toBe("Ordered 2 spools");
    expect(historyText({ ...added(0), spools: null, action: "on_order_changed" })).toBe(
      "Changed on order",
    );
  });

  it("says who did it, when, and what was on order after", () => {
    const now = new Date("2026-11-22T09:00:00Z");
    expect(historyWhen(added(2), now)).toBe("frank · Nov 21, 12:00 PM · 0 on order");
    expect(historyWhen({ ...added(2, null), on_order: 3 }, now)).toBe(
      "Nov 21, 12:00 PM · 3 on order",
    );
  });
});

describe("findInStore", () => {
  it("searches the store by the product's Bambu code", () => {
    expect(findInStore(STORE, product({ catalog_link: link() }))).toBe(
      "https://store.example/search?q=10100",
    );
  });

  it("is not offered without a Bambu code", () => {
    expect(findInStore(STORE, product({ catalog_link: link({ bambu_code: null }) }))).toBeNull();
    expect(findInStore(STORE, product({ catalog_link: null }))).toBeNull();
  });
});

describe("shoppingGroups", () => {
  it("puts Not in the catalog last, with its total and filament types", () => {
    const jade = lowItem(1, "Jade White", 1, 0, { catalog_link: link() });
    const red = lowItem(2, "Red", 2, 1);
    const blue = lowItem(3, "Blue", 1, 1);
    const list = shoppingList({
      lines: [{ name: "PLA Basic", to_buy: 2, items: [jade] }],
      not_in_catalog: [blue, red],
    });

    expect(shoppingGroups(list)).toEqual([
      { key: "line-0", name: "PLA Basic", toBuy: 2, items: [jade], showType: false },
      {
        key: "not-in-catalog",
        name: "Not in the catalog",
        toBuy: 3,
        items: [blue, red],
        showType: true,
      },
    ]);
  });

  it("leaves out Not in the catalog when it is empty", () => {
    expect(shoppingGroups(shoppingList())).toEqual([]);
  });
});
