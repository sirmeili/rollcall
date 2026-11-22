import { describe, expect, it } from "vitest";
import { findInStore, reasonText, shoppingGroups, spoolsText } from "#lib/shopping-list.ts";
import { product } from "../test/fixtures.ts";
import { link, lowItem, STORE, shoppingList } from "../test/shopping-fixtures.ts";

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
