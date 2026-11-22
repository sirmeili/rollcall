import { render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ShoppingList, ShoppingListItem } from "#lib/api/shopping.ts";
import { session } from "#lib/auth/session.svelte.ts";
import type { Role } from "#lib/roles.ts";
import { viewport } from "#lib/viewport.svelte.ts";
import { fakeFetch, me, product } from "../test/fixtures.ts";
import { added, requestReason, shoppingList } from "../test/shopping-fixtures.ts";

const ShoppingListPage = (await import("./shopping-list/+page.svelte")).default;

function jade(overrides: Partial<ShoppingListItem> = {}): ShoppingListItem {
  return {
    product: product({ id: 3, display_name: "Jade White PLA Basic", low_stock_threshold: 0 }),
    to_buy: 3,
    need: 3,
    on_order: 0,
    dismissed_need: null,
    new_since_dismissal: null,
    reasons: [requestReason(4, 2000), requestReason(null, 500)],
    size: { grams: 1000, source: "default" },
    history: [],
    ...overrides,
  };
}

const LIST: ShoppingList = shoppingList({ not_in_catalog: [jade()] });
const SIZED: ShoppingList = shoppingList({
  not_in_catalog: [
    jade({
      to_buy: 1,
      need: 1,
      size: { grams: 3000, source: "chosen" },
      history: [{ ...added(0), action: "size_changed", spools: null, size_g: 3000 }],
    }),
  ],
});

function serve(routes: Record<string, unknown> = {}) {
  const fetch = fakeFetch({ "GET /shopping-list": LIST, ...routes });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

function signedInAs(role: Role): void {
  session.user = me(role);
}

async function shown(): Promise<HTMLElement> {
  render(ShoppingListPage);
  await screen.findByText("Jade White PLA Basic");
  return screen.getByText("Jade White PLA Basic").closest("li") as HTMLElement;
}

beforeEach(() => signedInAs("editor"));

afterEach(() => {
  session.user = null;
  viewport().phone = false;
  vi.unstubAllGlobals();
});

describe("print requests on the shopping list", () => {
  it("links a request the viewer may see, and shows another as a print request", async () => {
    serve();
    const item = await shown();

    const named = within(item).getByRole("link", { name: "Lamp shade · 2000 g short" });
    expect(named).toHaveAttribute("href", "/requests/4");
    expect(within(item).getByText("A print request · 500 g short").closest("a")).toBeNull();
    expect(within(item).getByText("3")).toBeInTheDocument();
  });

  it("shows the size the item uses", async () => {
    serve();
    const item = await shown();

    expect(within(item).getByText("Size: 1000 g spools (the default)")).toBeInTheDocument();
  });
});

describe("choosing an item's size", () => {
  it("lets an Editor choose another size, which updates the item", async () => {
    const fetch = serve({ "PUT /shopping-list/items/3/size": SIZED });
    const item = await shown();

    await userEvent.click(within(item).getByRole("button", { name: "Change size" }));
    const size = within(item).getByRole("spinbutton", { name: "Size in grams" });
    expect(size).toHaveValue(1000);
    await userEvent.clear(size);
    await userEvent.type(size, "3000");
    await userEvent.click(within(item).getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Size: 3000 g spools (chosen)")).toBeInTheDocument();
    expect(screen.getByText("Size set to 3000 g")).toBeInTheDocument();
    expect(fetch.calls.at(-1)).toEqual({
      method: "PUT",
      path: "/shopping-list/items/3/size",
      body: { size_g: 3000 },
    });
  });

  it("refuses a size out of range before saving", async () => {
    const fetch = serve();
    const item = await shown();

    await userEvent.click(within(item).getByRole("button", { name: "Change size" }));
    const size = within(item).getByRole("spinbutton", { name: "Size in grams" });
    await userEvent.clear(size);
    await userEvent.type(size, "20000");

    expect(within(item).getByText("Size: a whole number of grams, 1 to 10,000.")).toBeVisible();
    expect(within(item).getByRole("button", { name: "Save" })).toBeDisabled();
    expect(fetch.calls.map((c) => c.method)).toEqual(["GET"]);
  });

  it("says when saving fails, and Cancel leaves the size as it was", async () => {
    serve({ "PUT /shopping-list/items/3/size": new Response("{}", { status: 500 }) });
    const item = await shown();

    await userEvent.click(within(item).getByRole("button", { name: "Change size" }));
    await userEvent.click(within(item).getByRole("button", { name: "Save" }));

    expect(await within(item).findByRole("alert")).toBeInTheDocument();
    await userEvent.click(within(item).getByRole("button", { name: "Cancel" }));
    expect(within(item).getByText("Size: 1000 g spools (the default)")).toBeInTheDocument();
  });

  it("gives Viewers no Change size", async () => {
    signedInAs("viewer");
    serve();
    const item = await shown();

    expect(within(item).getByText("Size: 1000 g spools (the default)")).toBeInTheDocument();
    expect(within(item).queryByRole("button", { name: "Change size" })).toBeNull();
  });

  it("offers Change size in a phone row's expanded view", async () => {
    viewport().phone = true;
    serve();
    render(ShoppingListPage);

    await userEvent.click(await screen.findByRole("button", { name: /Jade White PLA Basic/ }));

    expect(screen.getByRole("button", { name: "Change size" })).toBeInTheDocument();
  });
});
