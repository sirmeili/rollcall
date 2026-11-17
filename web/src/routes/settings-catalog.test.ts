import { render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SyncStatus } from "#lib/api/catalog.ts";
import type { GroupOut, SettingOut } from "#lib/api/settings.ts";
import { setTimeZone } from "#lib/format.ts";
import { fakeFetch } from "../test/fixtures.ts";

const SettingsPage = (await import("./settings/+page.svelte")).default;

const NEVER: SyncStatus = {
  last_success_at: null,
  last_attempt_at: null,
  last_result: null,
  last_reason: null,
  dataset_version: null,
  colors: 0,
};

const SYNCED: SyncStatus = {
  last_success_at: "2026-11-15T04:00:00Z",
  last_attempt_at: "2026-11-15T04:00:00Z",
  last_result: "updated",
  last_reason: null,
  dataset_version: "2026.11.15",
  colors: 304,
};

const FAILED: SyncStatus = {
  ...SYNCED,
  last_attempt_at: "2026-11-16T04:00:00Z",
  last_result: "failed",
  last_reason: "download incomplete",
};

function setting(key: string, value: string, source: SettingOut["source"]): SettingOut {
  return { key, value, secret: false, set: true, source, has_env: false, unreadable: false };
}

function catalogSettings(
  sync = "daily",
  cutoff = "10.0",
  source: SettingOut["source"] = "default",
): GroupOut {
  return {
    group: "catalog",
    settings: [setting("catalog_sync", sync, source), setting("similarity_cutoff", cutoff, source)],
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

/** The value shown under a status label, such as "Last attempt". */
function detail(term: string): string {
  return card().getByText(term).nextElementSibling?.textContent?.trim() ?? "";
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
  it("comes after Home Assistant and names its source and license", async () => {
    serve({ "GET /catalog/sync": SYNCED });
    render(SettingsPage);

    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings.indexOf("Catalog")).toBe(headings.indexOf("Home Assistant") + 1);
    expect(
      card().getByText("Catalog data from the Open Filament Database, used under the MIT license."),
    ).toBeInTheDocument();
  });

  it("shows the last success, the last attempt and the dataset version", async () => {
    serve({ "GET /catalog/sync": SYNCED });
    render(SettingsPage);

    await card().findByText("v2026.11.15");
    expect(detail("Last successful sync")).toBe("Nov 15, 4:00 AM");
    expect(detail("Last attempt")).toMatch(/^Nov 15, 4:00 AM\s+Updated$/);
    expect(detail("Dataset version")).toBe("v2026.11.15");
    expect(card().queryByRole("alert")).toBeNull();
  });

  it("says when the catalog has never synced", async () => {
    serve({ "GET /catalog/sync": NEVER });
    render(SettingsPage);

    expect(await card().findAllByText("Never")).toHaveLength(2);
    expect(detail("Dataset version")).toBe("—");
  });

  it("warns that the last attempt failed and which copy is kept", async () => {
    serve({ "GET /catalog/sync": FAILED });
    render(SettingsPage);

    expect(await card().findByRole("alert")).toHaveTextContent(
      "Last attempt failed: download incomplete. Keeping the copy from Nov 15.",
    );
    expect(detail("Last attempt")).toMatch(/^Nov 16, 4:00 AM\s+Failed: download incomplete$/);
    expect(detail("Last successful sync")).toBe("Nov 15, 4:00 AM");
  });

  it("says there is no copy when no sync has ever worked", async () => {
    serve({ "GET /catalog/sync": { ...FAILED, last_success_at: null, dataset_version: null } });
    render(SettingsPage);

    expect(await card().findByRole("alert")).toHaveTextContent(
      "Last attempt failed: download incomplete. There is no copy yet.",
    );
  });

  it("refreshes now and says it is up to date when nothing changed", async () => {
    const fetch = serve({
      "GET /catalog/sync": SYNCED,
      "POST /catalog/sync": {
        ...SYNCED,
        last_success_at: "2026-11-16T15:43:00Z",
        last_attempt_at: "2026-11-16T15:43:00Z",
        last_result: "not_modified",
      },
    });
    render(SettingsPage);

    await card().findByText("v2026.11.15");
    await userEvent.click(card().getByRole("button", { name: "Refresh now" }));

    expect(fetch.calls.at(-1)).toMatchObject({ method: "POST", path: "/catalog/sync" });
    expect(await card().findByText("Up to date. Nothing new since Nov 15.")).toBeInTheDocument();
    expect(detail("Last attempt")).toMatch(/^Nov 16, 3:43 PM\s+Not modified$/);
    expect(detail("Last successful sync")).toBe("Nov 16, 3:43 PM");
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
      "Sync failed: download incomplete.",
    );
    expect(card().getByRole("alert")).toHaveTextContent("Keeping the copy from Nov 15.");
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
    expect(card().getByRole("status")).toHaveTextContent("Checking for a new version…");
    answer(new Response(JSON.stringify({ ...SYNCED, last_result: "not_modified" })));
    expect(await card().findByText("Up to date. Nothing new since Nov 15.")).toBeInTheDocument();
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
    expect(form().getByText("From api.openfilamentdatabase.org, once a day.")).toBeInTheDocument();
    expect(
      form().getByText("Below 2 is barely visible; 2–10 is close; above 25 is clearly different."),
    ).toBeInTheDocument();
    expect(form().getAllByText("Default")).toHaveLength(2);
    expect(form().getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("explains each schedule", async () => {
    serve({ "GET /catalog/sync": SYNCED });
    render(SettingsPage);

    await screen.findByLabelText("Similarity cutoff");
    await userEvent.click(schedule("Weekly"));
    expect(form().getByText("From api.openfilamentdatabase.org, once a week.")).toBeInTheDocument();
    await userEvent.click(schedule("Off"));
    expect(
      form().getByText("The catalog stays as it is until you press Refresh now."),
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
    expect(form().getAllByText("Saved here")).toHaveLength(2);
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
});
