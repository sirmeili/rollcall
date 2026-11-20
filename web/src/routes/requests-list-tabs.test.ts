import { render, screen, waitFor, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Me } from "#lib/api/types.ts";
import { setTimeZone } from "#lib/format.ts";
import { viewport } from "#lib/viewport.svelte.ts";
import { me } from "../test/fixtures.ts";
import { row } from "../test/request-fixtures.ts";

const api = vi.hoisted(() => ({ listRequests: vi.fn() }));
vi.mock("#lib/api/requests.ts", async (original) => ({
  ...(await original<typeof import("#lib/api/requests.ts")>()),
  ...api,
}));

const { session } = await import("#lib/auth/session.svelte.ts");
const ListPage = (await import("./requests/+page.svelte")).default;

const SAM = me("viewer", { id: 2, username: "sam", requester: true, has_requests: true });
const DANA = me("editor", { id: 3, username: "dana" });
const FRANK = me("admin", { id: 1, username: "frank", requester: true });
const OPEN = [
  "Submitted",
  "Approved",
  "Waiting on Filament",
  "Queued",
  "Printing",
  "Done",
  "Failed",
];

function signIn(user: Me): void {
  session.user = user;
  session.loaded = true;
}

const ACTIVE = { tab: "active", statuses: [], mine: false };

function lastQuery(): unknown {
  return api.listRequests.mock.lastCall?.[0];
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"], now: new Date("2026-11-18T15:00:00Z") });
  setTimeZone("UTC");
  viewport().phone = false;
  api.listRequests.mockResolvedValue([row()]);
});
afterEach(() => {
  vi.useRealTimers();
  vi.resetAllMocks();
});

describe("Requests list tabs", () => {
  it("opens on the Active tab and switches to Closed, newest move first", async () => {
    signIn(SAM);
    render(ListPage);

    const tabs = await screen.findByRole("group", { name: "Show" });
    expect(within(tabs).getByRole("button", { name: "Active" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(lastQuery()).toEqual(ACTIVE);
    expect(await screen.findByText(/^request · /)).toHaveTextContent(
      "1 request · Most urgent first, then by needed-by date, then oldest first",
    );

    api.listRequests.mockResolvedValue([row({ status: "picked_up" }), row({ id: 42 })]);
    await userEvent.click(within(tabs).getByRole("button", { name: "Closed" }));

    expect(within(tabs).getByRole("button", { name: "Closed" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(lastQuery()).toEqual({ ...ACTIVE, tab: "closed" });
    expect(await screen.findByText(/^requests · /)).toHaveTextContent(
      "2 requests · Most recently closed first",
    );
  });

  it("gives a Requester no status filter and no Only mine", async () => {
    signIn(SAM);
    render(ListPage);

    await screen.findByRole("group", { name: "Show" });
    expect(screen.queryByRole("group", { name: "Filter by status" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Only mine" })).toBeNull();
  });

  it("lets Editors filter the Active tab by open statuses", async () => {
    signIn(DANA);
    render(ListPage);

    const filter = await screen.findByRole("group", { name: "Filter by status" });
    expect(
      within(filter)
        .getAllByRole("button")
        .map((b) => b.textContent?.trim()),
    ).toEqual(OPEN);
    expect(screen.queryByRole("button", { name: "Only mine" })).toBeNull();

    await userEvent.click(within(filter).getByRole("button", { name: "Queued" }));
    await userEvent.click(within(filter).getByRole("button", { name: "Failed" }));
    expect(within(filter).getByRole("button", { name: "Queued" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(lastQuery()).toEqual({ ...ACTIVE, statuses: ["queued", "failed"] });

    await userEvent.click(within(filter).getByRole("button", { name: "Queued" }));
    expect(lastQuery()).toEqual({ ...ACTIVE, statuses: ["failed"] });

    await userEvent.click(screen.getByRole("button", { name: "Closed" }));
    expect(screen.queryByRole("group", { name: "Filter by status" })).toBeNull();
    expect(lastQuery()).toEqual({ ...ACTIVE, tab: "closed" });
  });

  it("gives an Admin who is a Requester Only mine on both tabs", async () => {
    signIn(FRANK);
    render(ListPage);

    const mine = await screen.findByRole("button", { name: "Only mine" });
    await userEvent.click(mine);
    expect(mine).toHaveAttribute("aria-pressed", "true");
    expect(lastQuery()).toEqual({ ...ACTIVE, mine: true });

    await userEvent.click(screen.getByRole("button", { name: "Closed" }));
    expect(screen.getByRole("button", { name: "Only mine" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(lastQuery()).toEqual({ tab: "closed", statuses: [], mine: true });
  });
});

describe("Requests list empty states", () => {
  it.each([
    // The New request links: in the page head, and in an empty Active tab.
    [DANA, "active", "No active requests", 0],
    [FRANK, "active", "No active requests", 2],
    [SAM, "active", "You don't have any active requests", 2],
    [{ ...SAM, requester: false }, "active", "You don't have any active requests", 0],
    [DANA, "closed", "No closed requests", 0],
    [SAM, "closed", "You don't have any closed requests", 1],
  ])("explains an empty tab (%#)", async (user, tab, heading, links) => {
    signIn(user);
    api.listRequests.mockResolvedValue([]);
    render(ListPage);

    if (tab === "closed") {
      await userEvent.click(await screen.findByRole("button", { name: "Closed" }));
      await waitFor(() => expect(lastQuery()).toEqual({ ...ACTIVE, tab: "closed" }));
    }

    expect(await screen.findByRole("heading", { name: heading })).toBeVisible();
    expect(screen.queryAllByRole("link", { name: "New request" })).toHaveLength(links);
  });

  it("says when nothing matches the filters", async () => {
    signIn(FRANK);
    api.listRequests.mockResolvedValue([]);
    render(ListPage);

    await userEvent.click(await screen.findByRole("button", { name: "Only mine" }));

    expect(await screen.findByRole("heading", { name: "No matching requests" })).toBeVisible();
    expect(
      screen.getByText("Pick other statuses or turn off Only mine to see more."),
    ).toBeVisible();
  });
});
