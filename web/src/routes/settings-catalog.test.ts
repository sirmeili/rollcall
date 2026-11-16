import { render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SyncStatus } from "#lib/api/catalog.ts";
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

function serve(routes: Parameters<typeof fakeFetch>[0]) {
  const fetch = fakeFetch({
    "GET /settings/general": { group: "general", settings: [] },
    "GET /settings/scanners": { group: "scanners", settings: [] },
    "GET /settings/home-assistant": { group: "home-assistant", settings: [] },
    "GET /tokens": [],
    ...routes,
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

function card() {
  return within(screen.getByRole("region", { name: "Catalog" }));
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
