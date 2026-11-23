// Leaving a form with unsaved changes asks first: Back on the phone, a nav link, the
// browser's Back, Sign out, and Back on a dialog with changes. In-app navigation reaches the
// layout's guard as SvelteKit's `beforeNavigate` would call it.
import { cleanup, render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { createRawSnippet } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from "vitest";
import type { Me } from "#lib/api/types.ts";
import { browserBridge, setBridge } from "#lib/phone/bridge.ts";
import { savePairing } from "#lib/phone/pairing-store.ts";
import { fakeBridge, PAIRING, type FakeBridge } from "../test/fake-bridge.ts";
import { fakeFetch, me, spoolDetail, spoolRow } from "../test/fixtures.ts";
import { choice, request } from "../test/request-fixtures.ts";

/** A SvelteKit navigation, as `beforeNavigate` is given it. */
interface Navigation {
  type: "link" | "popstate" | "goto" | "leave";
  to: { url: URL } | null;
  delta?: number;
  willUnload: boolean;
  cancel: () => void;
}

const nav = vi.hoisted(() => ({
  page: { params: {} as Record<string, string>, url: new URL("https://localhost/") },
  goto: vi.fn(),
  guard: null as ((navigation: Navigation) => void) | null,
}));
vi.mock("$app/state", () => ({ page: nav.page }));
vi.mock("$app/navigation", () => ({
  goto: nav.goto,
  beforeNavigate: (guard: (navigation: Navigation) => void) => (nav.guard = guard),
}));

const { session } = await import("#lib/auth/session.svelte.ts");
const { phone } = await import("#lib/phone/phone-state.svelte.ts");
const Layout = (await import("./+layout.svelte")).default;
const NewRequestPage = (await import("./requests/new/+page.svelte")).default;
const SpoolPage = (await import("./spools/[id]/+page.svelte")).default;
const AccountPage = (await import("./account/+page.svelte")).default;
const RequestPage = (await import("./requests/[id]/+page.svelte")).default;

const SAM = me("viewer", { id: 2, username: "sam", requester: true, has_requests: true });
const children = createRawSnippet(() => ({ render: () => "<p>page content</p>" }));

/** The fake server's answers, which a test can add to. */
const routes: Record<string, unknown> = {};

/** The Layout at `path`, signed in as `user`, with `Page` rendered beside it. */
async function openAt(path: string, user: Me, Page: typeof NewRequestPage): Promise<void> {
  session.user = user;
  session.loaded = true;
  nav.page.url = new URL(path, "https://localhost");
  render(Layout, { children });
  await screen.findByText("page content");
  render(Page);
}

/** Navigate as SvelteKit would, through the layout's guard; true when it went ahead. */
function navigate(type: Navigation["type"], to: string | null, delta?: number): boolean {
  let cancelled = false;
  nav.guard!({
    type,
    to: to === null ? null : { url: new URL(to, "https://localhost") },
    delta,
    willUnload: type === "leave",
    cancel: () => (cancelled = true),
  });
  return !cancelled;
}

function warning(): HTMLElement | null {
  return screen.queryByRole("alertdialog", { name: "Leave without saving?" });
}

let go: MockInstance<(delta?: number) => void>;

/** Answer the warning. */
async function answer(button: "Stay" | "Leave"): Promise<void> {
  const shown = await screen.findByRole("alertdialog", { name: "Leave without saving?" });
  await userEvent.click(within(shown).getByRole("button", { name: button }));
}

beforeEach(() => {
  go = vi.spyOn(window.history, "go").mockImplementation(() => {});
  for (const key of Object.keys(routes)) delete routes[key];
  Object.assign(routes, {
    "GET /inventory": [],
    "GET /catalog": new Response(null, { status: 503 }),
    "GET /spools/1": spoolDetail(),
  });
  // In the phone app requests go to the paired server's address: answer them the same.
  const serve = fakeFetch(routes);
  vi.stubGlobal("fetch", (input: RequestInfo | URL, init?: RequestInit) =>
    serve(String(input).replace(/^https?:\/\/[^/]+/, ""), init),
  );
});

afterEach(() => {
  cleanup();
  go.mockRestore();
  session.user = null;
  session.loaded = false;
  vi.unstubAllGlobals();
  vi.resetAllMocks();
});

describe("Leaving a changed full-page form", () => {
  it("asks before following a nav link", async () => {
    await openAt("/requests/new", SAM, NewRequestPage);
    await userEvent.type(await screen.findByLabelText("Title"), "Dragon");

    expect(navigate("link", "/spools")).toBe(false);

    const dialog = await screen.findByRole("alertdialog", { name: "Leave without saving?" });
    expect(dialog).toHaveTextContent("Your changes will be lost.");
    expect(within(dialog).getByRole("button", { name: "Stay" })).toHaveFocus();
    expect(within(dialog).getByRole("button", { name: "Leave" })).toBeInTheDocument();
  });

  it("Stays on Stay, keeping the page, the form and history", async () => {
    await openAt("/requests/new", SAM, NewRequestPage);
    await userEvent.type(await screen.findByLabelText("Title"), "Dragon");
    navigate("link", "/spools");

    await answer("Stay");

    expect(warning()).toBeNull();
    expect(screen.getByLabelText("Title")).toHaveValue("Dragon");
    expect(nav.goto).not.toHaveBeenCalled();
    expect(go).not.toHaveBeenCalled();
  });

  it("Stays on Escape or a tap on the dimmed page", async () => {
    await openAt("/requests/new", SAM, NewRequestPage);
    await userEvent.type(await screen.findByLabelText("Title"), "Dragon");

    navigate("link", "/spools");
    await screen.findByRole("alertdialog");
    await userEvent.keyboard("{Escape}");
    expect(warning()).toBeNull();

    navigate("link", "/spools");
    await screen.findByRole("alertdialog");
    // The dimmed page comes before the dialog.
    await userEvent.click(screen.getAllByRole("button", { name: "Stay" })[0]);
    expect(warning()).toBeNull();
    expect(nav.goto).not.toHaveBeenCalled();
  });

  it("follows the link on Leave", async () => {
    await openAt("/requests/new", SAM, NewRequestPage);
    await userEvent.type(await screen.findByLabelText("Title"), "Dragon");
    navigate("link", "/spools");

    await answer("Leave");

    expect(warning()).toBeNull();
    expect(nav.goto).toHaveBeenCalledWith(new URL("https://localhost/spools"));
  });

  it("asks before the browser's Back, and goes back on Leave", async () => {
    await openAt("/requests/new", SAM, NewRequestPage);
    await userEvent.type(await screen.findByLabelText("Title"), "Dragon");

    expect(navigate("popstate", "/requests", -1)).toBe(false);
    await answer("Stay");
    expect(go).not.toHaveBeenCalled();

    navigate("popstate", "/requests", -1);
    await answer("Leave");
    expect(go).toHaveBeenCalledExactlyOnceWith(-1);
  });

  it("goes ahead once left, without asking again", async () => {
    await openAt("/requests/new", SAM, NewRequestPage);
    await userEvent.type(await screen.findByLabelText("Title"), "Dragon");
    navigate("popstate", "/requests", -1);
    await answer("Leave");

    // The browser's Back again, as Leave made it.
    expect(navigate("popstate", "/requests", -1)).toBe(true);
    expect(warning()).toBeNull();
  });

  it("never asks about the app's own navigation: a save or a redirect", async () => {
    await openAt("/requests/new", SAM, NewRequestPage);
    await userEvent.type(await screen.findByLabelText("Title"), "Dragon");

    expect(navigate("goto", "/login")).toBe(true);
    expect(warning()).toBeNull();
  });
});

describe("Leaving a changed inline form", () => {
  beforeEach(() => {
    nav.page.params = { id: "1" };
  });

  it("asks before leaving the page", async () => {
    await openAt("/spools/1", me("editor"), SpoolPage);
    await userEvent.type(await screen.findByLabelText("Location"), " 2");

    expect(navigate("link", "/")).toBe(false);
    expect(await screen.findByRole("alertdialog")).toBeInTheDocument();
  });

  it("doesn't ask once saved", async () => {
    routes["PATCH /spools/1"] = spoolDetail({ location: "Dry box 2" });
    await openAt("/spools/1", me("editor"), SpoolPage);
    const location = await screen.findByLabelText("Location");
    await userEvent.clear(location);
    await userEvent.type(location, "Dry box 2");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText("Saved");

    expect(navigate("link", "/")).toBe(true);
    expect(warning()).toBeNull();
  });

  it("still asks when the save is refused", async () => {
    routes["PATCH /spools/1"] = () => new Response(null, { status: 500 });
    await openAt("/spools/1", me("editor"), SpoolPage);
    await userEvent.type(await screen.findByLabelText("Location"), " 2");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText(/failed/i);

    expect(navigate("link", "/")).toBe(false);
  });
});

describe("No warning", () => {
  beforeEach(() => {
    nav.page.params = { id: "1" };
  });

  it("for a form that is unchanged", async () => {
    await openAt("/spools/1", me("editor"), SpoolPage);
    await userEvent.click(await screen.findByLabelText("Location"));

    expect(navigate("link", "/")).toBe(true);
    expect(warning()).toBeNull();
  });

  it("for a field changed back to its first value", async () => {
    await openAt("/spools/1", me("editor"), SpoolPage);
    const location = await screen.findByLabelText("Location");
    await userEvent.type(location, " 2");
    await userEvent.type(location, "{Backspace}{Backspace}");

    expect(navigate("link", "/")).toBe(true);
    expect(warning()).toBeNull();
  });
});

describe("Closing or reloading the tab", () => {
  beforeEach(() => {
    nav.page.params = { id: "1" };
  });

  it("has the browser ask only while a form has unsaved changes", async () => {
    await openAt("/spools/1", me("editor"), SpoolPage);
    const location = await screen.findByLabelText("Location");
    expect(navigate("leave", null)).toBe(true);

    await userEvent.type(location, " 2");
    expect(navigate("leave", null)).toBe(false);
    // The browser asks; the app's own warning doesn't show.
    expect(warning()).toBeNull();
  });
});
