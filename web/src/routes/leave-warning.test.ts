// Leaving a form with unsaved changes asks first: Back on the phone, a nav link, the
// browser's Back, Sign out, and Back on a dialog with changes. In-app navigation reaches the
// layout's guard as SvelteKit's `beforeNavigate` would call it.
import { cleanup, render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { createRawSnippet, type Component } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from "vitest";
import type { Me } from "#lib/api/types.ts";
import { browserBridge, setBridge } from "#lib/phone/bridge.ts";
import { savePairing } from "#lib/phone/pairing-store.ts";
import { fakeBridge, PAIRING, type FakeBridge } from "../test/fake-bridge.ts";
import { fakeFetch, me, spoolDetail, spoolRow } from "../test/fixtures.ts";
import { choice, request } from "../test/request-fixtures.ts";
import DelayedSaveForm from "../test/DelayedSaveForm.svelte";

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
const SettingsPage = (await import("./settings/+page.svelte")).default;

const SAM = me("viewer", { id: 2, username: "sam", requester: true, has_requests: true });
const children = createRawSnippet(() => ({ render: () => "<p>page content</p>" }));

/** The fake server's answers, which a test can add to. */
const routes: Record<string, unknown> = {};

/** The Layout at `path`, signed in as `user`, with `Page` rendered beside it. */
async function openAt<Props extends Record<string, unknown>>(
  path: string,
  user: Me,
  Page: Component<Props>,
  props?: Props,
): Promise<void> {
  session.user = user;
  session.loaded = true;
  nav.page.url = new URL(path, "https://localhost");
  render(Layout, { children });
  await screen.findByText("page content");
  render(Page, props);
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

describe("Saving resets the comparison", () => {
  const ADMIN = me("admin", { id: 1, username: "frank" });
  const NEVER_SYNCED = {
    last_success_at: null,
    last_attempt_at: null,
    last_result: null,
    last_reason: null,
    dataset_version: null,
  };

  /** A Home Assistant setting, as the server sends it. */
  function setting(key: string, fields: Record<string, unknown> = {}) {
    return {
      key,
      value: null,
      secret: false,
      set: false,
      source: "default",
      has_env: false,
      unreadable: false,
      ...fields,
    };
  }

  function homeAssistant(broker: { value: string; source: string }) {
    return {
      group: "home-assistant",
      settings: [
        setting("mqtt_url", { ...broker, set: true, has_env: true }),
        setting("ha_token", { secret: true, set: true, source: "env", has_env: true }),
      ],
    };
  }

  beforeEach(() => {
    nav.page.params = { id: "1" };
    const empty = (group: string) => ({ group, settings: [] });
    Object.assign(routes, {
      "GET /settings/general": empty("general"),
      "GET /settings/scanners": empty("scanners"),
      "GET /settings/email": empty("email"),
      "GET /settings/email/status": { on: false, last_success: null, last_failure: null },
      "GET /settings/catalog": empty("catalog"),
      "GET /catalog/sync": { colors: 0, ofdb: NEVER_SYNCED, bambustudio: NEVER_SYNCED },
      "GET /tokens": [],
      "GET /settings/home-assistant": homeAssistant({
        value: "mqtt://other:1883",
        source: "app",
      }),
    });
  });

  it("after a save made with a button rather than the form's Save", async () => {
    routes["DELETE /settings/home-assistant/mqtt_url"] = () => {
      routes["GET /settings/home-assistant"] = homeAssistant({
        value: "mqtt://broker:1883",
        source: "env",
      });
      return null;
    };
    await openAt("/settings", ADMIN, SettingsPage);

    await userEvent.click(
      await screen.findByRole("button", { name: "Use the .env value for MQTT broker" }),
    );
    await vi.waitFor(() =>
      expect(screen.getByLabelText("MQTT broker")).toHaveValue("mqtt://broker:1883"),
    );

    expect(navigate("link", "/")).toBe(true);
    expect(warning()).toBeNull();
  });

  it("still asks when a button's save is refused", async () => {
    routes["PUT /settings/home-assistant"] = () => new Response(null, { status: 500 });
    await openAt("/settings", ADMIN, SettingsPage);
    await userEvent.type(await screen.findByLabelText("MQTT broker"), "0");

    await userEvent.click(screen.getByRole("button", { name: "Clear Access token" }));
    await screen.findByRole("status");

    expect(navigate("link", "/")).toBe(false);
  });

  it("taking the value the server sends back as saved", async () => {
    routes["PATCH /spools/1"] = spoolDetail({ location: "Dry box 2" });
    await openAt("/spools/1", me("editor"), SpoolPage);
    const location = await screen.findByLabelText("Location");
    await userEvent.clear(location);
    await userEvent.type(location, "dry box 2");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await vi.waitFor(() => expect(location).toHaveValue("Dry box 2"));

    expect(navigate("link", "/")).toBe(true);
    expect(warning()).toBeNull();
  });

  it("asks again for a change made after saving", async () => {
    routes["PATCH /spools/1"] = spoolDetail({ location: "Dry box 2" });
    await openAt("/spools/1", me("editor"), SpoolPage);
    const location = await screen.findByLabelText("Location");
    await userEvent.clear(location);
    await userEvent.type(location, "Dry box 2");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText("Saved");

    await userEvent.type(location, "b");

    expect(navigate("link", "/")).toBe(false);
  });

  it("when the form's Save waits for something before it writes", async () => {
    routes["PUT /things/1"] = {};
    const before = () => new Promise<void>((done) => setTimeout(done, 20));
    await openAt("/things/1", me("editor"), DelayedSaveForm, { before });
    await userEvent.type(screen.getByLabelText("Name"), "Dragon");

    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByRole("status");

    expect(navigate("link", "/")).toBe(true);
    expect(warning()).toBeNull();
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

describe("Signing out with unsaved changes", () => {
  it("asks first, staying signed in on Stay and signing out on Leave", async () => {
    routes["POST /auth/logout"] = new Response(null, { status: 204 });
    await openAt("/account", me("editor"), AccountPage);
    await userEvent.type(screen.getByLabelText("Email address"), "frank@example.com");

    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await answer("Stay");
    expect(session.user).not.toBeNull();
    expect(screen.getByLabelText("Email address")).toHaveValue("frank@example.com");

    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await answer("Leave");
    await vi.waitFor(() => expect(nav.goto).toHaveBeenCalledWith("/login", { replaceState: true }));
    expect(session.user).toBeNull();
  });

  it("signs out straight away without changes", async () => {
    routes["POST /auth/logout"] = new Response(null, { status: 204 });
    await openAt("/account", me("editor"), AccountPage);

    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));

    await vi.waitFor(() => expect(nav.goto).toHaveBeenCalledWith("/login", { replaceState: true }));
    expect(warning()).toBeNull();
  });
});

describe("The phone's Back", () => {
  const ADMIN = me("admin", { id: 1, username: "frank" });
  let native: FakeBridge;
  let back: MockInstance<() => void>;

  /** As `openAt`, for a paired phone past the start screen. */
  async function openOnPhone(path: string, user: Me, Page: typeof NewRequestPage): Promise<void> {
    await savePairing(PAIRING, "AABB");
    await openAt(path, user, Page);
  }

  beforeEach(() => {
    native = fakeBridge();
    setBridge(native);
    back = vi.spyOn(window.history, "back").mockImplementation(() => {});
    routes["GET /devices/provisioning"] = { kdf_salt: "AABB" };
    routes["POST /devices/heartbeat"] = () => new Response(null, { status: 204 });
  });

  afterEach(async () => {
    cleanup();
    back.mockRestore();
    await phone.unpair();
    phone.loaded = false;
    setBridge(browserBridge);
  });

  it("asks before going back a page from a changed form, and Back on the warning Stays", async () => {
    await openOnPhone("/requests/new", SAM, NewRequestPage);
    await userEvent.type(await screen.findByLabelText("Title"), "Dragon");

    native.pressBack(true);
    // Going back a page is history.back(), which reaches the guard as the browser's Back.
    expect(back).toHaveBeenCalledOnce();
    expect(navigate("popstate", "/requests", -1)).toBe(false);
    await screen.findByRole("alertdialog", { name: "Leave without saving?" });

    native.pressBack(true);

    await vi.waitFor(() => expect(warning()).toBeNull());
    expect(back).toHaveBeenCalledOnce();
    expect(go).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Title")).toHaveValue("Dragon");
  });

  it("sends the app to the background without asking", async () => {
    await openOnPhone("/requests/new", SAM, NewRequestPage);
    await userEvent.type(await screen.findByLabelText("Title"), "Dragon");

    native.pressBack(false);

    expect(native.backgrounded).toBe(1);
    expect(warning()).toBeNull();
    expect(screen.getByLabelText("Title")).toHaveValue("Dragon");
  });

  describe("on the Move dialog", () => {
    beforeEach(() => {
      nav.page.params = { id: "41" };
      routes["GET /requests/41"] = request({
        moves: [{ to_status: "rejected", reason_required: true, photos: false }],
      });
    });

    async function openReject(): Promise<HTMLElement> {
      await openOnPhone("/requests/41", ADMIN, RequestPage);
      await userEvent.click(await screen.findByRole("button", { name: "Reject" }));
      return screen.getByRole("dialog", { name: "Reject this request?" });
    }

    it("asks before closing it with changes, keeping it on Stay", async () => {
      const dialog = await openReject();
      await userEvent.type(within(dialog).getByRole("textbox"), "Out of PLA");

      native.pressBack(true);
      await answer("Stay");

      expect(screen.getByRole("dialog", { name: "Reject this request?" })).toBe(dialog);
      expect(within(dialog).getByRole("textbox")).toHaveValue("Out of PLA");
      expect(back).not.toHaveBeenCalled();
    });

    it("closes it on Leave, without moving the request", async () => {
      const dialog = await openReject();
      await userEvent.type(within(dialog).getByRole("textbox"), "Out of PLA");

      native.pressBack(true);
      await answer("Leave");

      await vi.waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
      expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
      expect(back).not.toHaveBeenCalled();
    });

    it("closes it straight away without changes", async () => {
      await openReject();

      native.pressBack(true);

      await vi.waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
      expect(warning()).toBeNull();
    });
  });

  it("asks before closing the Holds dialog with changes", async () => {
    nav.page.params = { id: "41" };
    routes["GET /requests/41"] = request({
      status: "queued",
      can_change_holds: true,
      choices: [choice({ id: 1, name: "Blue PLA", product_id: 7, held: true, grams: 300 })],
    });
    routes["GET /spools?state=sealed&state=open&limit=200"] = {
      items: [spoolRow({ id: 12 })],
      total: 1,
    };
    await openOnPhone("/requests/41", ADMIN, RequestPage);
    await userEvent.click(await screen.findByRole("button", { name: "Edit holds for Blue PLA" }));
    const dialog = screen.getByRole("dialog", { name: "Holds for Blue PLA" });
    const spool = within(dialog).getByRole("combobox", { name: "Spool to hold" });
    await within(spool).findByRole("option", { name: /^#12 / });
    await userEvent.selectOptions(spool, "#12 Black PLA Basic · about 620 g left");

    native.pressBack(true);
    await answer("Stay");

    expect(screen.getByRole("dialog", { name: "Holds for Blue PLA" })).toBe(dialog);
  });
});
