// The layout picks the phone layout at 600px wide or less, and the header above that.
import { cleanup, render, screen, within } from "@testing-library/svelte";
import { createRawSnippet } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { viewport } from "#lib/viewport.svelte.ts";
import { me } from "../test/fixtures.ts";

const nav = vi.hoisted(() => ({
  page: { url: new URL("https://localhost/spools") },
  goto: vi.fn(),
}));
vi.mock("$app/state", () => ({ page: nav.page }));
vi.mock("$app/navigation", () => ({ goto: nav.goto, beforeNavigate: vi.fn() }));
vi.mock("#lib/review-badge.svelte.ts", () => ({
  reviewBadge: { count: 3, refresh: vi.fn() },
}));
// A plain browser unless a test makes it the Android app.
const phone = vi.hoisted(() => ({
  app: false,
  paired: false,
  loaded: true,
  server: null as string | null,
  reach: null as string | null,
  openOn: null,
  load: () => Promise.resolve(),
}));
vi.mock("#lib/phone/phone-state.svelte.ts", async (actual) => ({
  ...(await actual<object>()),
  phone,
}));

const { session } = await import("#lib/auth/session.svelte.ts");
const Layout = (await import("./+layout.svelte")).default;

const children = createRawSnippet(() => ({
  render: () => '<div class="pagehead"><h1>Spools</h1></div>',
}));

beforeEach(() => {
  session.user = me("admin");
  session.loaded = true;
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  Object.assign(phone, { app: false, paired: false, server: null, reach: null });
  viewport().phone = false;
  session.user = null;
  session.loaded = false;
});

describe("the layout's shell", () => {
  it("shows the header with its nav on a wide screen", () => {
    viewport().phone = false;
    render(Layout, { children });

    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "App" })).toBeNull();
    expect(screen.getByRole("main")).not.toHaveClass("phone");
  });

  it("shows the top bar and the bottom bar on a phone-sized screen", () => {
    viewport().phone = true;
    render(Layout, { children });

    expect(screen.queryByRole("navigation", { name: "Main" })).toBeNull();
    expect(screen.getByRole("link", { name: "RollCall, Inventory" })).toBeInTheDocument();
    const bar = screen.getByRole("navigation", { name: "App" });
    expect(bar).toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveClass("phone");
    // The page's own heading stays for screen readers.
    expect(screen.getByRole("heading", { name: "Spools" })).toBeInTheDocument();
    // No Scan in a plain browser.
    expect(screen.queryByRole("link", { name: "Scan" })).toBeNull();
  });

  describe("in the Android app", () => {
    /** Render the layout on a phone in the app, past its start screen. */
    async function renderInApp(paired: boolean): Promise<HTMLElement> {
      vi.useFakeTimers();
      Object.assign(phone, { app: true, paired, server: "https://rollcall.lan", reach: "online" });
      viewport().phone = true;
      render(Layout, { children });
      await vi.runAllTimersAsync();
      return screen.getByRole("navigation", { name: "App" });
    }

    it("offers Scan once the phone is paired", async () => {
      const bar = await renderInApp(true);
      expect(within(bar).getByRole("link", { name: "Scan" })).toHaveAttribute("href", "/scan");
    });

    it("counts an unpaired phone as Scan not available", async () => {
      const bar = await renderInApp(false);
      expect(within(bar).queryByRole("link", { name: "Scan" })).toBeNull();
      expect(within(bar).getByRole("link", { name: "Add spool" })).toHaveAttribute(
        "href",
        "/spools/new",
      );
    });
  });
});
