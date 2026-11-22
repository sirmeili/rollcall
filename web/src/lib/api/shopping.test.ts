import { afterEach, describe, expect, it, vi } from "vitest";
import { getShoppingList } from "#lib/api/shopping.ts";
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
});
