import { afterEach, describe, expect, it, vi } from "vitest";
import { addByHand, getShoppingList, removeHandReason } from "#lib/api/shopping.ts";
import { fakeFetch } from "../../test/fixtures.ts";

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
});
