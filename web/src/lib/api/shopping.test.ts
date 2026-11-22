import { afterEach, describe, expect, it, vi } from "vitest";
import {
  addByHand,
  addSuggestion,
  bringBack,
  dismissItem,
  dismissSuggestion,
  getShoppingList,
  removeHandReason,
  suggest,
  suggestionCount,
} from "#lib/api/shopping.ts";
import { fakeFetch } from "../../test/fixtures.ts";
import { shoppingList, suggestion } from "../../test/shopping-fixtures.ts";

afterEach(() => vi.unstubAllGlobals());

describe("shopping list API calls", () => {
  it("reads the list", async () => {
    const list = { lines: [], not_in_catalog: [], store_address: "https://store.example" };
    const fetch = fakeFetch({ "GET /shopping-list": list });
    vi.stubGlobal("fetch", fetch);

    expect(await getShoppingList()).toEqual(list);
    expect(fetch.calls).toEqual([{ method: "GET", path: "/shopping-list", body: undefined }]);
  });

  it("adds spools by hand to a product or a catalog color", async () => {
    const list = { lines: [], not_in_catalog: [], store_address: "https://store.example" };
    const fetch = fakeFetch({ "POST /shopping-list/hand-reasons": list });
    vi.stubGlobal("fetch", fetch);

    expect(await addByHand({ product_id: 4 }, 2)).toEqual(list);
    await addByHand({ catalog_color: "jade" }, 1);

    expect(fetch.calls.map((call) => call.body)).toEqual([
      { product_id: 4, spools: 2 },
      { catalog_color: "jade", spools: 1 },
    ]);
  });

  it("removes a hand-added reason", async () => {
    const list = { lines: [], not_in_catalog: [], store_address: "https://store.example" };
    const fetch = fakeFetch({ "DELETE /shopping-list/hand-reasons/7": list });
    vi.stubGlobal("fetch", fetch);

    expect(await removeHandReason(7)).toEqual(list);
    expect(fetch.calls).toEqual([
      { method: "DELETE", path: "/shopping-list/hand-reasons/7", body: undefined },
    ]);
  });

  it("dismisses an item and brings it back", async () => {
    const list = { lines: [], not_in_catalog: [], store_address: "https://store.example" };
    const fetch = fakeFetch({
      "POST /shopping-list/items/4/dismiss": list,
      "POST /shopping-list/items/4/bring-back": list,
    });
    vi.stubGlobal("fetch", fetch);

    expect(await dismissItem(4)).toEqual(list);
    expect(await bringBack(4)).toEqual(list);
    expect(fetch.calls).toEqual([
      { method: "POST", path: "/shopping-list/items/4/dismiss", body: undefined },
      { method: "POST", path: "/shopping-list/items/4/bring-back", body: undefined },
    ]);
  });

  it("suggests spools of a product or a catalog color", async () => {
    const list = shoppingList();
    const fetch = fakeFetch({ "POST /shopping-list/suggestions": list });
    vi.stubGlobal("fetch", fetch);

    expect(await suggest({ product_id: 4 }, 2)).toEqual(list);
    await suggest({ catalog_color: "jade" }, 1);

    expect(fetch.calls.map((call) => call.body)).toEqual([
      { product_id: 4, spools: 2 },
      { catalog_color: "jade", spools: 1 },
    ]);
  });

  it("adds and dismisses a suggestion", async () => {
    const list = shoppingList();
    const fetch = fakeFetch({
      "POST /shopping-list/suggestions/3/add": list,
      "POST /shopping-list/suggestions/4/dismiss": list,
    });
    vi.stubGlobal("fetch", fetch);

    expect(await addSuggestion(3)).toEqual(list);
    expect(await dismissSuggestion(4)).toEqual(list);
    expect(fetch.calls.map((call) => `${call.method} ${call.path}`)).toEqual([
      "POST /shopping-list/suggestions/3/add",
      "POST /shopping-list/suggestions/4/dismiss",
    ]);
  });

  it("counts the open suggestions", async () => {
    const list = shoppingList({ suggestions: [suggestion(1), suggestion(2)] });
    vi.stubGlobal("fetch", fakeFetch({ "GET /shopping-list": list }));

    expect(await suggestionCount()).toBe(2);
  });
});
