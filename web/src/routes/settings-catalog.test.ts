import { render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SourceStatus, SyncStatus } from "#lib/api/catalog.ts";
import type { GroupOut, SettingOut } from "#lib/api/settings.ts";
import { setTimeZone } from "#lib/format.ts";
import { fakeFetch } from "../test/fixtures.ts";

const SettingsPage = (await import("./settings/+page.svelte")).default;

const NEVER_SOURCE: SourceStatus = {
  last_success_at: null,
  last_attempt_at: null,
  last_result: null,
  last_reason: null,
  dataset_version: null,
};

const OFDB_SYNCED: SourceStatus = {
  last_success_at: "2026-11-15T04:00:00Z",
  last_attempt_at: "2026-11-15T04:00:00Z",
  last_result: "updated",
  last_reason: null,
  dataset_version: "2026.11.15",
};

const BAMBUSTUDIO_SYNCED: SourceStatus = {
  ...OFDB_SYNCED,
  last_success_at: "2026-11-12T04:00:00Z",
  last_attempt_at: "2026-11-12T04:00:00Z",
  dataset_version: null,
};

const NEVER: SyncStatus = { colors: 0, ofdb: NEVER_SOURCE, bambustudio: NEVER_SOURCE };

const SYNCED: SyncStatus = { colors: 304, ofdb: OFDB_SYNCED, bambustudio: BAMBUSTUDIO_SYNCED };

function failed(source: SourceStatus, reason: string): SourceStatus {
  return {
    ...source,
    last_attempt_at: "2026-11-16T04:00:00Z",
    last_result: "failed",
    last_reason: reason,
  };
}

const FAILED: SyncStatus = { ...SYNCED, ofdb: failed(OFDB_SYNCED, "download incomplete") };

const NOT_MODIFIED: SourceStatus = {
  last_success_at: "2026-11-16T15:43:00Z",
  last_attempt_at: "2026-11-16T15:43:00Z",
  last_result: "not_modified",
  last_reason: null,
  dataset_version: null,
};

function setting(key: string, value: string, source: SettingOut["source"]): SettingOut {
  return { key, value, secret: false, set: true, source, has_env: false, unreadable: false };
}

function catalogSettings(
  sync = "daily",
  cutoff = "10.0",
  source: SettingOut["source"] = "default",
  store = "https://us.store.bambulab.com",
): GroupOut {
  return {
    group: "catalog",
    settings: [
      setting("catalog_sync", sync, source),
      setting("similarity_cutoff", cutoff, source),
      setting("store_address", store, source),
    ],
  };
}

function serve(routes: Parameters<typeof fakeFetch>[0]) {
  const fetch = fakeFetch({
    "GET /settings/general": { group: "general", settings: [] },
    "GET /settings/scanners": { group: "scanners", settings: [] },
    "GET /settings/home-assistant": { group: "home-assistant", settings: [] },
    "GET /tokens": [],
    "GET /settings/catalog": catalogSettings(),
    ...routes,
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

function card() {
  return within(screen.getByRole("region", { name: "Catalog" }));
}

function form() {
  return within(screen.getByRole("form", { name: "Catalog" }));
}

function schedule(name: string) {
  return within(form().getByRole("group", { name: "Automatic sync" })).getByRole("button", {
    name,
  });
}

const OFDB = "Open Filament Database";
const BAMBUSTUDIO = "BambuStudio color codes";

/** Waits for the sources' status to load. */
async function loaded(): Promise<void> {
  await card().findByRole("region", { name: OFDB });
}

/** One source's status block. */
function source(name: string = OFDB) {
  return within(card().getByRole("region", { name }));
}

/** The value shown under a status label, such as "Last attempt", for one source. */
function detail(term: string, name: string = OFDB): string {
  return source(name).getByText(term).nextElementSibling?.textContent?.trim() ?? "";
}

beforeEach(() => {
  vi.useFakeTimers({ now: new Date("2026-11-16T15:43:00Z"), shouldAdvanceTime: true });
  setTimeZone("UTC");
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  setTimeZone(undefined);
});

describe("Settings page, Catalog card", () => {
  it("comes after Home Assistant and names both sources and their licenses", async () => {
    serve({ "GET /catalog/sync": SYNCED });
    render(SettingsPage);

    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings.indexOf("Catalog")).toBe(headings.indexOf("Home Assistant") + 1);
    expect(
      card().getByText(
        "Local copies of the Open Filament Database's Bambu Lab colors and BambuStudio's Bambu codes, for the Catalog page.",
      ),
    ).toBeInTheDocument();
    expect(
      card().getByText("Catalog data from the Open Filament Database, used under the MIT license."),
    ).toBeInTheDocument();
    expect(
      card().getByText(
        "Bambu codes from BambuStudio's color code list, used under the AGPL-3.0 license.",
      ),
    ).toBeInTheDocument();
    await loaded();
    expect(source(OFDB).getByText("api.openfilamentdatabase.org")).toBeInTheDocument();
    expect(source(BAMBUSTUDIO).getByText("raw.githubusercontent.com")).toBeInTheDocument();
  });

  it("shows each source's last success and last attempt, and OFDB's dataset version", async () => {
    serve({ "GET /catalog/sync": SYNCED });
    render(SettingsPage);

    await card().findByText("v2026.11.15");
    expect(detail("Last successful sync")).toBe("Nov 15, 4:00 AM");
    expect(detail("Last attempt")).toMatch(/^Nov 15, 4:00 AM\s+Updated$/);
    expect(detail("Dataset version")).toBe("v2026.11.15");
    expect(detail("Last successful sync", BAMBUSTUDIO)).toBe("Nov 12, 4:00 AM");
    expect(detail("Last attempt", BAMBUSTUDIO)).toMatch(/^Nov 12, 4:00 AM\s+Updated$/);
    expect(source(BAMBUSTUDIO).queryByText("Dataset version")).toBeNull();
    expect(card().queryByRole("alert")).toBeNull();
  });

  it("says when the catalog has never synced", async () => {
    serve({ "GET /catalog/sync": NEVER });
    render(SettingsPage);

    await loaded();
    expect(source(OFDB).getAllByText("Never")).toHaveLength(2);
    expect(source(BAMBUSTUDIO).getAllByText("Never")).toHaveLength(2);
    expect(detail("Dataset version")).toBe("—");
  });

  it("warns under BambuStudio only when only its list failed", async () => {
    serve({
      "GET /catalog/sync": {
        ...SYNCED,
        bambustudio: failed(BAMBUSTUDIO_SYNCED, "the file's format changed"),
      },
    });
    render(SettingsPage);

    await loaded();
    expect(source(BAMBUSTUDIO).getByRole("alert")).toHaveTextContent(
      "Last attempt failed: the file's format changed. Keeping the copy from Nov 12.",
    );
    expect(source(OFDB).queryByRole("alert")).toBeNull();
    expect(detail("Last attempt", BAMBUSTUDIO)).toMatch(
      /^Nov 16, 4:00 AM\s+Failed: the file's format changed$/,
    );
  });

  it("warns that the last attempt failed and which copy is kept", async () => {
    serve({ "GET /catalog/sync": FAILED });
    render(SettingsPage);

    await loaded();
    expect(source(OFDB).getByRole("alert")).toHaveTextContent(
      "Last attempt failed: download incomplete. Keeping the copy from Nov 15.",
    );
    expect(source(BAMBUSTUDIO).queryByRole("alert")).toBeNull();
    expect(detail("Last attempt")).toMatch(/^Nov 16, 4:00 AM\s+Failed: download incomplete$/);
    expect(detail("Last successful sync")).toBe("Nov 15, 4:00 AM");
  });

  it("says there is no copy when no sync has ever worked", async () => {
    serve({
      "GET /catalog/sync": {
        ...FAILED,
        ofdb: { ...FAILED.ofdb, last_success_at: null, dataset_version: null },
      },
    });
    render(SettingsPage);

    expect(await card().findByRole("alert")).toHaveTextContent(
      "Last attempt failed: download incomplete. There is no copy yet.",
    );
  });

  it("refreshes both sources and says when neither has anything new", async () => {
    const fetch = serve({
      "GET /catalog/sync": SYNCED,
      "POST /catalog/sync": {
        ...SYNCED,
        ofdb: { ...NOT_MODIFIED, dataset_version: "2026.11.15" },
        bambustudio: NOT_MODIFIED,
      },
    });
    render(SettingsPage);

    await card().findByText("v2026.11.15");
    await userEvent.click(card().getByRole("button", { name: "Refresh now" }));

    expect(fetch.calls.at(-1)).toMatchObject({ method: "POST", path: "/catalog/sync" });
    expect(
      await card().findByText("Up to date. Nothing new in either source."),
    ).toBeInTheDocument();
    expect(detail("Last attempt")).toMatch(/^Nov 16, 3:43 PM\s+Not modified$/);
    expect(detail("Last successful sync")).toBe("Nov 16, 3:43 PM");
    expect(detail("Last attempt", BAMBUSTUDIO)).toMatch(/^Nov 16, 3:43 PM\s+Not modified$/);
  });

  it("reports a new BambuStudio list on its own", async () => {
    serve({
      "GET /catalog/sync": SYNCED,
      "POST /catalog/sync": {
        ...SYNCED,
        ofdb: { ...NOT_MODIFIED, dataset_version: "2026.11.15" },
        bambustudio: { ...NOT_MODIFIED, last_result: "updated" },
      },
    });
    render(SettingsPage);

    await card().findByText("v2026.11.15");
    await userEvent.click(card().getByRole("button", { name: "Refresh now" }));

    expect(await card().findByRole("status")).toHaveTextContent(
      "Updated BambuStudio's color codes.",
    );
  });

  it("reports a new version after Refresh now", async () => {
    serve({
      "GET /catalog/sync": NEVER,
      "POST /catalog/sync": SYNCED,
    });
    render(SettingsPage);

    await card().findAllByText("Never");
    await userEvent.click(card().getByRole("button", { name: "Refresh now" }));

    expect(await card().findByRole("status")).toHaveTextContent(
      "Updated to v2026.11.15: 304 catalog colors.",
    );
  });

  it("reports a failed Refresh now and keeps the warning", async () => {
    serve({ "GET /catalog/sync": SYNCED, "POST /catalog/sync": FAILED });
    render(SettingsPage);

    await card().findByText("v2026.11.15");
    await userEvent.click(card().getByRole("button", { name: "Refresh now" }));

    expect(await card().findByRole("status")).toHaveTextContent(
      "OFDB sync failed: download incomplete.",
    );
    expect(source(OFDB).getByRole("alert")).toHaveTextContent("Keeping the copy from Nov 15.");
  });

  it("says so when a sync is already running", async () => {
    serve({
      "GET /catalog/sync": SYNCED,
      "POST /catalog/sync": new Response(
        JSON.stringify({ detail: "A catalog sync is already running" }),
        { status: 409 },
      ),
    });
    render(SettingsPage);

    await card().findByText("v2026.11.15");
    await userEvent.click(card().getByRole("button", { name: "Refresh now" }));

    expect(await card().findByRole("status")).toHaveTextContent(
      "A catalog sync is already running.",
    );
  });

  it("disables Refresh now while it runs", async () => {
    let answer: (value: Response) => void = () => {};
    serve({
      "GET /catalog/sync": SYNCED,
      "POST /catalog/sync": () => new Promise<Response>((resolve) => (answer = resolve)),
    });
    render(SettingsPage);

    await card().findByText("v2026.11.15");
    const button = card().getByRole("button", { name: "Refresh now" });
    await userEvent.click(button);

    expect(button).toBeDisabled();
    expect(card().getByRole("status")).toHaveTextContent(
      "Checking both sources for a new version…",
    );
    answer(
      new Response(JSON.stringify({ ...SYNCED, ofdb: NOT_MODIFIED, bambustudio: NOT_MODIFIED })),
    );
    expect(
      await card().findByText("Up to date. Nothing new in either source."),
    ).toBeInTheDocument();
    expect(button).toBeEnabled();
  });

  it("shows why the status could not be read", async () => {
    serve({});
    render(SettingsPage);

    expect(await card().findByRole("alert")).toHaveTextContent("Not found");
  });
});

describe("Settings page, Catalog card form", () => {
  it("shows the schedule and cutoff in use and where they come from", async () => {
    serve({ "GET /catalog/sync": SYNCED });
    render(SettingsPage);

    expect(await screen.findByLabelText("Similarity cutoff")).toHaveValue(10);
    expect(schedule("Daily")).toHaveAttribute("aria-pressed", "true");
    expect(schedule("Off")).toHaveAttribute("aria-pressed", "false");
    expect(
      form().getByText(
        "From api.openfilamentdatabase.org and BambuStudio's color code list on GitHub (raw.githubusercontent.com), once a day.",
      ),
    ).toBeInTheDocument();
    expect(
      form().getByText("Below 2 is barely visible; 2–10 is close; above 25 is clearly different."),
    ).toBeInTheDocument();
    expect(form().getAllByText("Default")).toHaveLength(3);
    expect(form().getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("explains each schedule", async () => {
    serve({ "GET /catalog/sync": SYNCED });
    render(SettingsPage);

    await screen.findByLabelText("Similarity cutoff");
    await userEvent.click(schedule("Weekly"));
    expect(
      form().getByText(
        "From api.openfilamentdatabase.org and BambuStudio's color code list on GitHub (raw.githubusercontent.com), once a week.",
      ),
    ).toBeInTheDocument();
    await userEvent.click(schedule("Off"));
    expect(
      form().getByText("The catalog and Bambu codes stay as they are until you press Refresh now."),
    ).toBeInTheDocument();
    expect(schedule("Off")).toHaveAttribute("aria-pressed", "true");
    expect(schedule("Daily")).toHaveAttribute("aria-pressed", "false");
  });

  it("saves only what changed", async () => {
    const fetch = serve({
      "GET /catalog/sync": SYNCED,
      "PUT /settings/catalog": catalogSettings("off", "2.5", "app"),
    });
    render(SettingsPage);

    const cutoff = await screen.findByLabelText("Similarity cutoff");
    await userEvent.click(schedule("Off"));
    await userEvent.clear(cutoff);
    await userEvent.type(cutoff, "2.5");
    await userEvent.click(form().getByRole("button", { name: "Save" }));

    expect(fetch.calls.at(-1)).toEqual({
      method: "PUT",
      path: "/settings/catalog",
      body: { values: { catalog_sync: "off", similarity_cutoff: "2.5" }, clear: [] },
    });
    expect(await form().findByRole("status")).toHaveTextContent(
      "Saved. The Catalog page uses the new cutoff now.",
    );
    expect(form().getAllByText("Saved here")).toHaveLength(3);
    expect(form().getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it.each(["60", "0.4", ""])("refuses a cutoff of %j before saving", async (text) => {
    serve({ "GET /catalog/sync": SYNCED });
    render(SettingsPage);

    const cutoff = await screen.findByLabelText("Similarity cutoff");
    await userEvent.clear(cutoff);
    if (text) await userEvent.type(cutoff, text);

    expect(form().getByRole("alert")).toHaveTextContent(
      "Similarity cutoff: enter a number from 0.5 to 50.",
    );
    expect(cutoff).toHaveAttribute("aria-invalid", "true");
    expect(form().getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("shows the server's reason when it refuses a cutoff", async () => {
    serve({
      "GET /catalog/sync": SYNCED,
      "PUT /settings/catalog": () =>
        new Response(
          JSON.stringify({
            detail: { problems: { similarity_cutoff: "use a number from 0.5 to 50" } },
          }),
          { status: 422 },
        ),
    });
    render(SettingsPage);

    const cutoff = await screen.findByLabelText("Similarity cutoff");
    await userEvent.clear(cutoff);
    await userEvent.type(cutoff, "12");
    await userEvent.click(form().getByRole("button", { name: "Save" }));

    expect(await form().findByRole("alert")).toHaveTextContent(
      "Similarity cutoff: use a number from 0.5 to 50.",
    );
  });

  it("shows the Store address in use, with what it does", async () => {
    serve({ "GET /catalog/sync": SYNCED });
    render(SettingsPage);

    const store = await screen.findByLabelText("Store address");
    expect(store).toHaveValue("https://us.store.bambulab.com");
    expect(
      form().getByText(
        "Find in store searches this store. Only https addresses, no path. Bambu's store picks your region from where you are, so change this only if it doesn't.",
      ),
    ).toBeInTheDocument();
  });

  it("saves a Store address without its trailing slash", async () => {
    const fetch = serve({
      "GET /catalog/sync": SYNCED,
      "PUT /settings/catalog": catalogSettings(
        "daily",
        "10.0",
        "app",
        "https://eu.store.bambulab.com",
      ),
    });
    render(SettingsPage);

    const store = await screen.findByLabelText("Store address");
    await userEvent.clear(store);
    await userEvent.type(store, "https://eu.store.bambulab.com/");
    await userEvent.click(form().getByRole("button", { name: "Save" }));

    expect(fetch.calls.at(-1)).toEqual({
      method: "PUT",
      path: "/settings/catalog",
      body: { values: { store_address: "https://eu.store.bambulab.com" }, clear: [] },
    });
    expect(await form().findByRole("status")).toHaveTextContent("Saved.");
    expect(store).toHaveValue("https://eu.store.bambulab.com");
  });

  it.each([
    "http://us.store.bambulab.com",
    "https://us.store.bambulab.com/search",
    "https://us.store.bambulab.com?q=1",
    "https://us.store.bambulab.com#top",
    "https://me@us.store.bambulab.com",
    "us.store.bambulab.com",
    "",
  ])("refuses a Store address of %j before saving", async (text) => {
    serve({ "GET /catalog/sync": SYNCED });
    render(SettingsPage);

    const store = await screen.findByLabelText("Store address");
    await userEvent.clear(store);
    if (text) await userEvent.type(store, text);

    expect(form().getByRole("alert")).toHaveTextContent(
      "Enter an https address with no path, like https://us.store.bambulab.com",
    );
    expect(store).toHaveAttribute("aria-invalid", "true");
    expect(form().getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("shows the message when the server refuses a Store address", async () => {
    serve({
      "GET /catalog/sync": SYNCED,
      "PUT /settings/catalog": () =>
        new Response(
          JSON.stringify({
            detail: { problems: { store_address: "use an https address with no path" } },
          }),
          { status: 422 },
        ),
    });
    render(SettingsPage);

    const store = await screen.findByLabelText("Store address");
    await userEvent.clear(store);
    await userEvent.type(store, "https://xn--strange.example");
    await userEvent.click(form().getByRole("button", { name: "Save" }));

    expect(await form().findByRole("alert")).toHaveTextContent(
      "Enter an https address with no path, like https://us.store.bambulab.com",
    );
  });
});
