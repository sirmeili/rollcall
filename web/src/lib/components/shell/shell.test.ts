// The phone layout (docs/mockups/mobile-web/): the top bar, the bottom bar and the menu sheet.
import { cleanup, render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import type { Me } from "#lib/api/types.ts";
import PhoneNav from "#lib/components/shell/PhoneNav.svelte";
import PhoneTopBar from "#lib/components/shell/PhoneTopBar.svelte";
import { menuGroups, pageTitle } from "#lib/nav.ts";
import { PHONE_QUERY, Viewport } from "#lib/viewport.svelte.ts";
import { me } from "../../../test/fixtures.ts";

const ADMIN: Me = me("admin");
const VIEWER: Me = me("viewer", { id: 2, username: "bob" });

afterEach(cleanup);

describe("page titles and menu groups", () => {
  it("names each page for the top bar", () => {
    expect(pageTitle("/")).toBe("Inventory");
    expect(pageTitle("/spools/7")).toBe("Spools");
    expect(pageTitle("/spools/new")).toBe("Add a spool");
    expect(pageTitle("/account")).toBe("Account");
    expect(pageTitle("/somewhere")).toBe("RollCall");
  });

  it("puts the Admin pages apart, and only for Admins", () => {
    const admin = menuGroups(me("admin"));
    expect(admin.main.map((item) => item.label)).toEqual([
      "Inventory",
      "Spools",
      "Products",
      "Catalog",
      "Requests",
      "Review",
      "Shopping list",
      "Activity",
    ]);
    expect(admin.admin.map((item) => item.label)).toEqual(["Devices", "Users", "Settings"]);
    expect(menuGroups(me("viewer")).admin).toEqual([]);
    expect(menuGroups(null)).toEqual({ main: [], admin: [] });
  });
});

describe("the phone-sized screen", () => {
  function media(matches: boolean) {
    const listeners: ((event: MediaQueryListEvent) => void)[] = [];
    const list = {
      matches,
      addEventListener: (_: string, listener: (event: MediaQueryListEvent) => void) =>
        listeners.push(listener),
    } as unknown as MediaQueryList;
    let asked = "";
    const matchMedia = (query: string) => {
      asked = query;
      return list;
    };
    return { matchMedia, listeners, asked: () => asked };
  }

  it("follows the window across 600px", () => {
    const fake = media(true);
    const screenSize = new Viewport(fake.matchMedia);
    expect(fake.asked()).toBe(PHONE_QUERY);
    expect(PHONE_QUERY).toBe("(max-width: 600px)");
    expect(screenSize.phone).toBe(true);

    fake.listeners[0]({ matches: false } as MediaQueryListEvent);
    expect(screenSize.phone).toBe(false);
  });

  it("is not a phone where the browser cannot tell", () => {
    expect(new Viewport(undefined).phone).toBe(false);
  });
});

describe("the top bar", () => {
  it("shows the mark, linking home, and the page title", () => {
    render(PhoneTopBar, { title: "Spools" });
    expect(screen.getByRole("link", { name: "RollCall, Inventory" })).toHaveAttribute("href", "/");
    expect(screen.getByText("Spools")).toBeInTheDocument();
  });
});

describe("the bottom bar", () => {
  it("has Menu and the user around the centre", () => {
    render(PhoneNav, { user: ADMIN, pathname: "/", reviewCount: 0 });
    const nav = screen.getByRole("navigation", { name: "App" });

    expect(within(nav).getByRole("button", { name: "Menu" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(within(nav).getByRole("link", { name: "frank" })).toHaveAttribute("href", "/account");
    expect(nav.children).toHaveLength(3);
  });

  it("offers Scan and Add spool on Inventory and Spools to an Editor who can scan", async () => {
    const bar = render(PhoneNav, { user: me("editor"), pathname: "/", reviewCount: 0, scan: true });
    const nav = screen.getByRole("navigation", { name: "App" });

    for (const pathname of ["/", "/spools"]) {
      await bar.rerender({ pathname });
      expect(within(nav).getByRole("link", { name: "Scan" }), pathname).toHaveAttribute(
        "href",
        "/scan",
      );
      expect(within(nav).getByRole("link", { name: "Add spool" }), pathname).toHaveAttribute(
        "href",
        "/spools/new",
      );
      expect(nav.children).toHaveLength(3);
    }
  });

  it("offers a Viewer who can scan Scan alone on Inventory and Spools", async () => {
    const bar = render(PhoneNav, { user: VIEWER, pathname: "/", reviewCount: 0, scan: true });
    const nav = screen.getByRole("navigation", { name: "App" });

    for (const pathname of ["/", "/spools"]) {
      await bar.rerender({ pathname });
      expect(within(nav).getByRole("link", { name: "Scan" })).toHaveAttribute("href", "/scan");
      expect(within(nav).queryByRole("link", { name: "Add spool" })).toBeNull();
    }
  });

  it("offers a single Add spool on Inventory and Spools when Scan isn't available", async () => {
    const bar = render(PhoneNav, { user: ADMIN, pathname: "/", reviewCount: 0 });
    const nav = screen.getByRole("navigation", { name: "App" });

    for (const pathname of ["/", "/spools"]) {
      await bar.rerender({ pathname });
      expect(within(nav).getByRole("link", { name: "Add spool" })).toHaveAttribute(
        "href",
        "/spools/new",
      );
      expect(within(nav).queryByRole("link", { name: "Scan" })).toBeNull();
    }
  });

  it("has no centre on Inventory or Spools for a Viewer when Scan isn't available", async () => {
    const bar = render(PhoneNav, { user: VIEWER, pathname: "/", reviewCount: 0 });
    const nav = screen.getByRole("navigation", { name: "App" });

    for (const pathname of ["/", "/spools"]) {
      await bar.rerender({ pathname });
      expect(within(nav).getAllByRole("link")).toHaveLength(1);
      expect(nav.children).toHaveLength(3);
    }
  });

  it("offers a Requester New request on the Requests list and a request, never Scan", async () => {
    const bar = render(PhoneNav, {
      user: me("viewer", { requester: true }),
      pathname: "/requests",
      reviewCount: 0,
      scan: true,
    });
    const nav = screen.getByRole("navigation", { name: "App" });

    expect(within(nav).getByRole("link", { name: "New request" })).toHaveAttribute(
      "href",
      "/requests/new",
    );
    expect(within(nav).queryByRole("link", { name: "Scan" })).toBeNull();

    await bar.rerender({ pathname: "/requests/12" });
    expect(within(nav).getByRole("link", { name: "New request" })).toBeInTheDocument();
    expect(within(nav).queryByRole("link", { name: "Scan" })).toBeNull();
  });

  it("has no centre button on the Requests pages for someone who can't submit", async () => {
    const bar = render(PhoneNav, {
      user: ADMIN,
      pathname: "/requests",
      reviewCount: 0,
      scan: true,
    });
    const nav = screen.getByRole("navigation", { name: "App" });
    const centreless = () => {
      const links = within(nav).getAllByRole("link");
      expect(links).toHaveLength(1);
      expect(links[0]).toHaveAccessibleName("frank");
    };

    centreless();
    await bar.rerender({ pathname: "/requests/12" });
    centreless();
    // Menu and the user keep their places around the empty centre.
    expect(nav.children).toHaveLength(3);
  });

  it("has no centre button on the other pages, with Scan available or not", async () => {
    const bar = render(PhoneNav, { user: ADMIN, pathname: "/", reviewCount: 0 });
    const nav = screen.getByRole("navigation", { name: "App" });
    const pages = [
      "/spools/7",
      "/spools/new",
      "/products",
      "/products/3",
      "/catalog",
      "/review",
      "/shopping-list",
      "/activity",
      "/account",
      "/devices",
      "/settings",
    ];

    for (const scan of [false, true]) {
      for (const pathname of pages) {
        await bar.rerender({ pathname, scan });
        expect(within(nav).getAllByRole("link"), `${pathname}, scan ${scan}`).toHaveLength(1);
        expect(within(nav).queryByRole("button", { name: /New/ })).toBeNull();
        expect(nav.children).toHaveLength(3);
      }
    }
  });

  it("offers an Admin New user on Users, and only there", async () => {
    const bar = render(PhoneNav, { user: ADMIN, pathname: "/users", reviewCount: 0, scan: true });
    const nav = screen.getByRole("navigation", { name: "App" });

    expect(within(nav).getByRole("button", { name: "New user" })).toBeInTheDocument();
    expect(within(nav).queryByRole("link", { name: "Scan" })).toBeNull();
    expect(nav.children).toHaveLength(3);

    await bar.rerender({ pathname: "/settings" });
    expect(within(nav).queryByRole("button", { name: "New user" })).toBeNull();
  });

  it("offers no New user to someone who can't open Users", () => {
    render(PhoneNav, { user: me("editor"), pathname: "/users", reviewCount: 0 });
    expect(screen.queryByRole("button", { name: "New user" })).toBeNull();
  });

  it("has no centre button on the request form, whose own buttons take its place", () => {
    render(PhoneNav, {
      user: me("viewer", { requester: true }),
      pathname: "/requests/new",
      reviewCount: 0,
      scan: true,
    });
    const nav = screen.getByRole("navigation", { name: "App" });

    expect(within(nav).queryByRole("link", { name: "New request" })).toBeNull();
    expect(within(nav).queryByRole("link", { name: "Scan" })).toBeNull();
    expect(nav.children).toHaveLength(3);
  });

  it("marks Menu while suggestions are open, and counts them on the Shopping list", async () => {
    render(PhoneNav, { user: VIEWER, pathname: "/", reviewCount: 0, shoppingCount: 3 });

    const menu = screen.getByRole("button", { name: "Menu" });
    expect(menu.querySelector(".dot")).not.toBeNull();
    await userEvent.click(menu);
    expect(screen.getByRole("link", { name: "Shopping list, 3 suggested" })).toBeInTheDocument();
  });

  it("marks Menu while Review has items waiting", () => {
    render(PhoneNav, { user: ADMIN, pathname: "/", reviewCount: 3, shoppingCount: 0 });

    expect(screen.getByRole("button", { name: "Menu" }).querySelector(".dot")).not.toBeNull();
  });

  it("puts no mark on Menu when nothing waits", () => {
    render(PhoneNav, { user: VIEWER, pathname: "/", reviewCount: 0 });

    expect(screen.getByRole("button", { name: "Menu" }).querySelector(".dot")).toBeNull();
  });

  it("marks the user on Account", () => {
    render(PhoneNav, { user: ADMIN, pathname: "/account", reviewCount: 0 });
    expect(screen.getByRole("link", { name: "frank" })).toHaveAttribute("aria-current", "page");
  });

  it("opens the menu with every page an Admin may open, the current one marked", async () => {
    render(PhoneNav, { user: ADMIN, pathname: "/spools/7", reviewCount: 4, requestCount: 2 });

    await userEvent.click(screen.getByRole("button", { name: "Menu" }));

    const menu = screen.getByRole("dialog", { name: "Menu" });
    const pages = within(menu).getByRole("navigation", { name: "Pages" });
    expect(within(pages).getAllByRole("link")).toHaveLength(8);
    expect(within(pages).getByRole("link", { name: "Shopping list" })).toHaveAttribute(
      "href",
      "/shopping-list",
    );
    expect(within(pages).getByRole("link", { name: "Review, 4 waiting" })).toHaveAttribute(
      "href",
      "/review",
    );
    expect(within(pages).getByRole("link", { name: "Requests, 2 submitted" })).toHaveAttribute(
      "href",
      "/requests",
    );
    const spools = within(pages).getByRole("link", { name: "Spools" });
    expect(spools).toHaveAttribute("aria-current", "page");
    expect(spools).toHaveFocus();
    const admin = within(menu).getByRole("navigation", { name: "Admin pages" });
    expect(
      within(admin)
        .getAllByRole("link")
        .map((link) => link.textContent),
    ).toEqual(["Devices", "Users", "Settings"]);
    expect(screen.getByRole("button", { name: "Close" })).toHaveAttribute("aria-expanded", "true");
  });

  it("starts the menu with Scanner and Add spool, for an Editor who can scan", async () => {
    render(PhoneNav, { user: me("editor"), pathname: "/review", reviewCount: 0, scan: true });
    await userEvent.click(screen.getByRole("button", { name: "Menu" }));

    const shortcuts = screen.getByRole("navigation", { name: "Shortcuts" });
    const links = within(shortcuts).getAllByRole("link");
    expect(links.map((link) => [link.textContent, link.getAttribute("href")])).toEqual([
      ["Scanner", "/scan"],
      ["Add spool", "/spools/new"],
    ]);
    // The row comes before the pages.
    const menu = screen.getByRole("dialog", { name: "Menu" });
    expect(within(menu).getAllByRole("navigation")[0]).toBe(shortcuts);
  });

  it("shows only the shortcuts that apply in the menu, and no row when none do", async () => {
    const shortcuts = async (user: Me, scan: boolean): Promise<string[]> => {
      const bar = render(PhoneNav, { user, pathname: "/review", reviewCount: 0, scan });
      await userEvent.click(screen.getByRole("button", { name: "Menu" }));
      const row = screen.queryByRole("navigation", { name: "Shortcuts" });
      const labels = row
        ? within(row)
            .getAllByRole("link")
            .map((link) => link.textContent!)
        : [];
      bar.unmount();
      return labels;
    };

    expect(await shortcuts(VIEWER, true)).toEqual(["Scanner"]);
    expect(await shortcuts(ADMIN, false)).toEqual(["Add spool"]);
    expect(await shortcuts(VIEWER, false)).toEqual([]);
  });

  it("shows Requests in the menu to a Viewer who is a Requester", async () => {
    render(PhoneNav, { user: me("viewer", { requester: true }), pathname: "/", reviewCount: 0 });
    await userEvent.click(screen.getByRole("button", { name: "Menu" }));

    expect(screen.getByRole("link", { name: "Requests" })).toHaveAttribute("href", "/requests");
  });

  it("hides the Admin pages from a Viewer", async () => {
    render(PhoneNav, { user: VIEWER, pathname: "/", reviewCount: 0 });
    await userEvent.click(screen.getByRole("button", { name: "Menu" }));

    expect(screen.queryByRole("navigation", { name: "Admin pages" })).toBeNull();
    expect(screen.queryByText("Admin")).toBeNull();
    expect(screen.getByRole("link", { name: "Inventory" })).toHaveFocus();
  });

  it("closes with Close, the dimmed page, Escape or a page link, focus back on Menu", async () => {
    render(PhoneNav, { user: ADMIN, pathname: "/", reviewCount: 0 });
    const open = () => userEvent.click(screen.getByRole("button", { name: "Menu" }));

    await open();
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByRole("button", { name: "Menu" })).toHaveFocus();

    await open();
    await userEvent.click(screen.getByRole("button", { name: "Close the menu" }));
    expect(screen.queryByRole("dialog")).toBeNull();

    await open();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByRole("button", { name: "Menu" })).toHaveFocus();

    await open();
    const products = screen.getByRole("link", { name: "Products" });
    products.addEventListener("click", (event) => event.preventDefault());
    await userEvent.click(products);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("keeps Tab among the menu's links", async () => {
    render(PhoneNav, { user: VIEWER, pathname: "/", reviewCount: 0 });
    await userEvent.click(screen.getByRole("button", { name: "Menu" }));
    const first = screen.getByRole("link", { name: "Inventory" });
    const last = screen.getByRole("link", { name: "Activity" });

    await userEvent.tab({ shift: true });
    expect(last).toHaveFocus();
    await userEvent.tab();
    expect(first).toHaveFocus();
    await userEvent.tab();
    expect(screen.getByRole("link", { name: "Spools" })).toHaveFocus();
    await userEvent.keyboard("a"); // other keys do nothing
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("closes when the page changes", async () => {
    const bar = render(PhoneNav, { user: ADMIN, pathname: "/", reviewCount: 0 });
    await userEvent.click(screen.getByRole("button", { name: "Menu" }));

    await bar.rerender({ pathname: "/spools" });

    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
