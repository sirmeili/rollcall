import { render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { session } from "#lib/auth/session.svelte.ts";
import { viewport } from "#lib/viewport.svelte.ts";
import { fakeFetch, me } from "../test/fixtures.ts";
import { link, lowItem, shoppingList } from "../test/shopping-fixtures.ts";

const ShoppingListPage = (await import("./shopping-list/+page.svelte")).default;

const LIST = shoppingList({
  lines: [
    {
      name: "PLA Basic",
      to_buy: 2,
      items: [
        lowItem(1, "Black PLA Basic", 1, 1, { catalog_link: link() }),
        lowItem(31, "Jade White PLA Basic", 1, 1, { catalog_link: link() }),
      ],
    },
  ],
});

const scrolled = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fakeFetch({ "GET /shopping-list": LIST }));
  Element.prototype.scrollIntoView = function (this: Element) {
    scrolled(this.id);
  };
  session.user = me("viewer");
  window.location.hash = "#shopping-item-31";
});

afterEach(() => {
  window.location.hash = "";
  session.user = null;
  viewport().phone = false;
  scrolled.mockReset();
  vi.unstubAllGlobals();
});

describe("a link to a shopping list item", () => {
  it("scrolls to the item it names", async () => {
    render(ShoppingListPage);

    await screen.findByText("Jade White PLA Basic");
    await vi.waitFor(() => expect(scrolled).toHaveBeenCalledWith("shopping-item-31"));
  });

  it("expands the item it names on a phone", async () => {
    viewport().phone = true;
    render(ShoppingListPage);

    const row = await screen.findByRole("button", { name: /Jade White PLA Basic/ });
    expect(row).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: /Black PLA Basic/ })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    await vi.waitFor(() => expect(scrolled).toHaveBeenCalledWith("shopping-item-31"));
  });
});
