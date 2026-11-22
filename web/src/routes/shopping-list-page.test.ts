import { render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ShoppingList } from "#lib/api/shopping.ts";
import { session } from "#lib/auth/session.svelte.ts";
import { viewport } from "#lib/viewport.svelte.ts";
import { fakeFetch, me } from "../test/fixtures.ts";
import { link, lowItem, shoppingList } from "../test/shopping-fixtures.ts";

const ShoppingListPage = (await import("./shopping-list/+page.svelte")).default;

const LIST: ShoppingList = shoppingList({
  lines: [
    {
      name: "PLA Basic",
      to_buy: 3,
      items: [
        lowItem(1, "Jade White", 2, 1, { catalog_link: link() }),
        lowItem(2, "Plain Grey", 1, 1, {
          catalog_link: link({ uuid: "grey", name: "Grey", bambu_code: null }),
        }),
      ],
    },
    {
      name: "PLA Matte",
      to_buy: 1,
      items: [
        lowItem(3, "Ivory Matte", 1, 1, {
          catalog_link: link({
            uuid: "ivory",
            name: "Ivory",
            line: "PLA Matte",
            bambu_code: "11100",
          }),
        }),
      ],
    },
  ],
  not_in_catalog: [lowItem(4, "Red PETG", 3, 0, { filament_type: "PETG" })],
});

function serve(list: ShoppingList | Response = LIST) {
  const fetch = fakeFetch({ "GET /shopping-list": list });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

function group(name: string): HTMLElement {
  return screen.getByRole("region", { name: new RegExp(`^${name}`) });
}

function itemNames(region: HTMLElement): string[] {
  return [...region.querySelectorAll(".name")].map((name) => name.textContent ?? "");
}

function item(name: string): HTMLElement {
  return screen.getByText(name).closest("li") as HTMLElement;
}

beforeEach(() => {
  session.user = me("viewer");
});

afterEach(() => {
  session.user = null;
  viewport().phone = false;
  vi.unstubAllGlobals();
});

describe("the shopping list page", () => {
  it("groups items by filament line with each line's total, then Not in the catalog", async () => {
    serve();
    render(ShoppingListPage);

    await screen.findByText("Jade White");
    const regions = screen.getAllByRole("region").map((r) => r.getAttribute("aria-label"));
    expect(regions).toEqual([
      "PLA Basic, 3 to buy",
      "PLA Matte, 1 to buy",
      "Not in the catalog, 4 to buy",
    ]);
    expect(itemNames(group("PLA Basic"))).toEqual(["Jade White", "Plain Grey"]);
    expect(itemNames(group("Not in the catalog"))).toEqual(["Red PETG"]);
    expect(within(group("Not in the catalog")).getByText("PETG")).toBeInTheDocument();
    expect(within(group("PLA Basic")).queryByText("PLA")).toBeNull();
  });

  it("shows each item's to buy and its reasons", async () => {
    serve();
    render(ShoppingListPage);

    await screen.findByText("Jade White");
    const jade = item("Jade White");
    expect(within(jade).getByText("2", { selector: ".buy" })).toBeInTheDocument();
    expect(within(jade).getByText("to buy")).toBeInTheDocument();
    expect(
      within(jade).getByText("Low stock: 1 sealed, threshold 2 · 2 spools"),
    ).toBeInTheDocument();
  });

  it("offers Find in store only for an item whose product has a Bambu code", async () => {
    serve();
    render(ShoppingListPage);

    await screen.findByText("Jade White");
    expect(within(item("Jade White")).getByRole("link", { name: /Find in store/ })).toHaveAttribute(
      "href",
      "https://store.example/search?q=10100",
    );
    expect(within(item("Plain Grey")).queryByRole("link", { name: /Find in store/ })).toBeNull();
    expect(within(item("Red PETG")).queryByRole("link", { name: /Find in store/ })).toBeNull();
  });

  it("shows its filament lines as headings that do not collapse", async () => {
    serve();
    render(ShoppingListPage);

    expect(await screen.findByRole("heading", { name: /^PLA Basic/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^PLA Basic/ })).toBeNull();
  });

  it("says it is loading until the list arrives", async () => {
    let answer: (list: ShoppingList) => void = () => {};
    vi.stubGlobal(
      "fetch",
      fakeFetch({ "GET /shopping-list": () => new Promise((resolve) => (answer = resolve)) }),
    );
    render(ShoppingListPage);

    expect(screen.getByText("Loading…")).toBeInTheDocument();
    answer(LIST);
    expect(await screen.findByText("Jade White")).toBeInTheDocument();
  });

  it("says when there is nothing to buy", async () => {
    serve(shoppingList());
    render(ShoppingListPage);

    expect(await screen.findByText("Nothing to buy.")).toBeInTheDocument();
    expect(screen.queryAllByRole("region")).toEqual([]);
  });

  it("reports a failed read and tries again", async () => {
    serve(new Response("{}", { status: 500 }));
    render(ShoppingListPage);

    const alert = await screen.findByRole("alert");
    serve();
    await userEvent.click(within(alert).getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Jade White")).toBeInTheDocument();
  });
});

describe("the shopping list on a phone", () => {
  beforeEach(() => {
    viewport().phone = true;
  });

  function row(name: string): HTMLElement {
    return screen.getByRole("button", { name: new RegExp(name) });
  }

  it("shows compact rows that expand one at a time", async () => {
    serve();
    render(ShoppingListPage);

    await screen.findByText("Jade White");
    expect(screen.queryByText("Low stock: 1 sealed, threshold 2 · 2 spools")).toBeNull();
    expect(row("Jade White")).toHaveAttribute("aria-expanded", "false");

    await userEvent.click(row("Jade White"));
    expect(row("Jade White")).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Low stock: 1 sealed, threshold 2 · 2 spools")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Find in store/ })).toBeInTheDocument();

    await userEvent.click(row("Red PETG"));
    expect(row("Jade White")).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Low stock: 1 sealed, threshold 2 · 2 spools")).toBeNull();
    expect(screen.getByText("Low stock: 0 sealed, threshold 3 · 4 spools")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Find in store/ })).toBeNull();

    await userEvent.click(row("Red PETG"));
    expect(row("Red PETG")).toHaveAttribute("aria-expanded", "false");
  });

  it("collapses and expands a filament line", async () => {
    serve();
    render(ShoppingListPage);

    await screen.findByText("Jade White");
    const head = screen.getByRole("button", { name: /^PLA Basic/ });
    expect(head).toHaveAttribute("aria-expanded", "true");

    await userEvent.click(head);
    expect(head).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Jade White")).toBeNull();
    expect(screen.getByText("Ivory Matte")).toBeInTheDocument();

    await userEvent.click(head);
    expect(screen.getByText("Jade White")).toBeInTheDocument();
  });
});
