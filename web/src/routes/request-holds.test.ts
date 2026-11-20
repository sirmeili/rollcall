import { render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "#lib/api/client.ts";
import type { Choice, HistoryEntry, PrintRequest } from "#lib/api/requests.ts";
import type { Me, SpoolRow } from "#lib/api/types.ts";
import { setTimeZone } from "#lib/format.ts";
import { viewport } from "#lib/viewport.svelte.ts";
import { me, spoolRow } from "../test/fixtures.ts";
import { choice, request } from "../test/request-fixtures.ts";

const nav = vi.hoisted(() => ({
  page: { params: { id: "41" } as Record<string, string>, url: new URL("https://localhost/") },
  goto: vi.fn(),
}));
vi.mock("$app/state", () => ({ page: nav.page }));
vi.mock("$app/navigation", () => ({ goto: nav.goto }));

const api = vi.hoisted(() => ({
  getRequest: vi.fn(),
  setChoiceGrams: vi.fn(),
  addHold: vi.fn(),
  changeHold: vi.fn(),
  removeHold: vi.fn(),
  listSpools: vi.fn(),
}));
vi.mock("#lib/api/requests.ts", async (original) => ({
  ...(await original<typeof import("#lib/api/requests.ts")>()),
  getRequest: api.getRequest,
  setChoiceGrams: api.setChoiceGrams,
  addHold: api.addHold,
  changeHold: api.changeHold,
  removeHold: api.removeHold,
}));
vi.mock("#lib/api/stock.ts", async (original) => ({
  ...(await original<typeof import("#lib/api/stock.ts")>()),
  listSpools: api.listSpools,
}));

const { session } = await import("#lib/auth/session.svelte.ts");
const DetailPage = (await import("./requests/[id]/+page.svelte")).default;

const FRANK = me("admin", { id: 1, username: "frank" });
const DANA = me("editor", { id: 3, username: "dana" });
const SAM = me("viewer", { id: 2, username: "sam", requester: true, has_requests: true });

function signIn(user: Me): void {
  session.user = user;
  session.loaded = true;
}

function blue(fields: Partial<Choice> = {}): Choice {
  return choice({
    id: 1,
    kind: "product",
    name: "Blue PLA",
    product_id: 7,
    sealed: 2,
    open: 1,
    held: true,
    grams: 300,
    short_g: 0,
    holds: [{ id: 5, spool_id: 12, product_id: 7, product_name: "Blue PLA", grams: 300 }],
    available_g: 700,
    ...fields,
  });
}

function queued(fields: Partial<PrintRequest> = {}): PrintRequest {
  return request({ status: "queued", choices: [blue()], can_change_holds: true, ...fields });
}

function spool(id: number, name: string, grams: number | null): SpoolRow {
  const made = spoolRow({ id, grams_left_g: grams });
  return { ...made, product: { ...made.product, display_name: name } };
}

const SPOOLS = [
  spool(12, "Blue PLA", 1000),
  spool(15, "Blue PLA", null),
  spool(20, "Navy PLA", 800),
];

function holdsChanged(username: string): HistoryEntry {
  return {
    kind: "holds_changed",
    username,
    at: "2026-11-18T14:00:00Z",
    fields: null,
    from_value: null,
    to_value: null,
    note: null,
    automatic: false,
  };
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"], now: new Date("2026-11-18T15:00:00Z") });
  setTimeZone("UTC");
  viewport().phone = false;
  nav.page.params = { id: "41" };
  api.listSpools.mockResolvedValue({ items: SPOOLS, total: 3, limit: 200, offset: 0 });
});
afterEach(() => {
  vi.useRealTimers();
  vi.resetAllMocks();
});

/** Open the holds editor for Blue PLA. */
async function openEditor(): Promise<HTMLElement> {
  await userEvent.click(await screen.findByRole("button", { name: "Edit holds for Blue PLA" }));
  return screen.getByRole("dialog", { name: "Holds for Blue PLA" });
}

function holdRow(dialog: HTMLElement, name: string): HTMLElement {
  return within(dialog).getByRole("group", { name });
}

describe("Changing holds", () => {
  it("offers only an Admin the editor", async () => {
    signIn(DANA);
    api.getRequest.mockResolvedValue(queued({ can_change_holds: false }));
    render(DetailPage);

    await screen.findByRole("list", { name: "Holds for Blue PLA" });
    expect(screen.queryByRole("button", { name: /Edit holds/ })).toBeNull();
  });

  it("lists the spools on the shelf to hold, with their grams left", async () => {
    signIn(FRANK);
    api.getRequest.mockResolvedValue(queued());
    render(DetailPage);

    const dialog = await openEditor();
    const add = within(dialog).getByRole("combobox", { name: "Spool to hold" });
    await within(add).findByRole("option", { name: "#20 Navy PLA · about 800 g left" });
    expect(api.listSpools).toHaveBeenCalledWith({ states: ["sealed", "open"], limit: 200 });
    expect(within(add).getByRole("option", { name: "#15 Blue PLA · grams unknown" })).toBeTruthy();
  });

  it("still shows a held spool when the spools can't be listed, and sends empty grams as 0", async () => {
    signIn(FRANK);
    api.listSpools.mockRejectedValue(new ApiError(0, ""));
    api.getRequest.mockResolvedValue(queued());
    api.changeHold.mockResolvedValue(queued());
    api.setChoiceGrams.mockResolvedValue(queued());
    render(DetailPage);

    const dialog = await openEditor();
    const row = holdRow(dialog, "Hold on spool #12");
    const spools = within(row).getByRole("combobox", { name: "Spool" });
    expect(within(spools).getByRole("option", { name: "#12 Blue PLA" })).toBeTruthy();
    expect(
      within(within(dialog).getByRole("combobox", { name: "Spool to hold" })).getAllByRole(
        "option",
      ),
    ).toHaveLength(1);
    await userEvent.clear(within(row).getByRole("spinbutton", { name: "Grams" }));
    await userEvent.click(within(row).getByRole("button", { name: "Save" }));
    await userEvent.clear(within(dialog).getByLabelText("Grams for the whole quantity"));
    await userEvent.click(within(dialog).getByRole("button", { name: "Hold again" }));

    expect(api.changeHold).toHaveBeenCalledWith(41, "queued", 5, 12, 0);
    expect(api.setChoiceGrams).toHaveBeenCalledWith(41, "queued", 1, 0);
  });

  it("holds new grams for a choice again", async () => {
    signIn(FRANK);
    api.getRequest.mockResolvedValue(queued());
    api.setChoiceGrams.mockResolvedValue(
      queued({ choices: [blue({ grams: 800, short_g: 500 })], history: [holdsChanged("frank")] }),
    );
    render(DetailPage);

    const dialog = await openEditor();
    const grams = within(dialog).getByLabelText("Grams for the whole quantity");
    expect(grams).toHaveValue(300);
    await userEvent.clear(grams);
    await userEvent.type(grams, "800");
    await userEvent.click(within(dialog).getByRole("button", { name: "Hold again" }));

    expect(api.setChoiceGrams).toHaveBeenCalledWith(41, "queued", 1, 800);
    expect(await screen.findByText("Short 500 g")).toBeVisible();
    expect(screen.getByText("Holds changed by frank")).toBeVisible();
  });

  it("swaps a hold to another spool with new grams", async () => {
    signIn(FRANK);
    api.getRequest.mockResolvedValue(queued());
    api.changeHold.mockResolvedValue(queued());
    render(DetailPage);

    const dialog = await openEditor();
    const row = holdRow(dialog, "Hold on spool #12");
    await within(row).findByRole("option", { name: "#20 Navy PLA · about 800 g left" });
    await userEvent.selectOptions(within(row).getByRole("combobox", { name: "Spool" }), "20");
    const grams = within(row).getByRole("spinbutton", { name: "Grams" });
    await userEvent.clear(grams);
    await userEvent.type(grams, "250");
    await userEvent.click(within(row).getByRole("button", { name: "Save" }));

    expect(api.changeHold).toHaveBeenCalledWith(41, "queued", 5, 20, 250);
  });

  it("removes a hold", async () => {
    signIn(FRANK);
    api.getRequest.mockResolvedValue(queued());
    api.removeHold.mockResolvedValue(queued({ choices: [blue({ holds: [], short_g: 300 })] }));
    render(DetailPage);

    const dialog = await openEditor();
    await userEvent.click(
      within(holdRow(dialog, "Hold on spool #12")).getByRole("button", { name: "Remove" }),
    );

    expect(api.removeHold).toHaveBeenCalledWith(41, "queued", 5);
    expect(await within(dialog).findByText("Nothing held")).toBeVisible();
  });

  it("holds a spool of another product", async () => {
    signIn(FRANK);
    api.getRequest.mockResolvedValue(queued({ status: "waiting_on_filament" }));
    api.addHold.mockResolvedValue(queued());
    render(DetailPage);

    const dialog = await openEditor();
    const add = within(dialog).getByRole("combobox", { name: "Spool to hold" });
    const button = within(dialog).getByRole("button", { name: "Add hold" });
    expect(button).toBeDisabled();
    await within(add).findByRole("option", { name: "#20 Navy PLA · about 800 g left" });
    await userEvent.selectOptions(add, "20");
    await userEvent.type(within(dialog).getByLabelText("Grams to hold"), "100");
    await userEvent.click(button);

    expect(api.addHold).toHaveBeenCalledWith(41, "waiting_on_filament", 1, 20, 100);
  });

  it("shows what the server found wrong, in the editor", async () => {
    signIn(FRANK);
    api.getRequest.mockResolvedValue(queued());
    api.setChoiceGrams.mockRejectedValue(
      new ApiError(422, "", { problems: { grams: "Grams must be 1 to 100,000." } }),
    );
    api.removeHold.mockRejectedValue(new ApiError(0, ""));
    render(DetailPage);

    const dialog = await openEditor();
    await userEvent.click(within(dialog).getByRole("button", { name: "Hold again" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "Grams must be 1 to 100,000.",
    );
    await userEvent.click(within(dialog).getByRole("button", { name: "Remove" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Cannot reach the server.");
  });

  it("closes, says so and reloads when the request has changed meanwhile", async () => {
    signIn(FRANK);
    api.getRequest
      .mockResolvedValueOnce(queued())
      .mockResolvedValueOnce(queued({ status: "printing", can_change_holds: false }));
    api.removeHold.mockRejectedValue(
      new ApiError(409, "This request has changed. Reload to see it."),
    );
    render(DetailPage);

    const dialog = await openEditor();
    await userEvent.click(within(dialog).getByRole("button", { name: "Remove" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This request has changed. Reload to see it.",
    );
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(api.getRequest).toHaveBeenCalledTimes(2);
    await vi.waitFor(() =>
      expect(screen.getByText("Status:").parentElement).toHaveTextContent("Printing"),
    );
  });

  it("closes with Close or Escape", async () => {
    signIn(FRANK);
    api.getRequest.mockResolvedValue(queued());
    render(DetailPage);

    const dialog = await openEditor();
    await userEvent.click(within(dialog).getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    await openEditor();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("keeps Tab inside the editor", async () => {
    signIn(FRANK);
    api.getRequest.mockResolvedValue(queued());
    render(DetailPage);

    const dialog = await openEditor();
    const grams = within(dialog).getByLabelText("Grams for the whole quantity");
    const close = within(dialog).getByRole("button", { name: "Close" });
    expect(grams).toHaveFocus();
    await userEvent.tab({ shift: true });
    expect(close).toHaveFocus();
    await userEvent.tab();
    expect(grams).toHaveFocus();
    await userEvent.tab();
    expect(within(dialog).getByRole("button", { name: "Hold again" })).toHaveFocus();
  });

  it("closes once the request no longer holds filament", async () => {
    signIn(FRANK);
    api.getRequest.mockResolvedValue(queued());
    api.removeHold.mockResolvedValue(queued({ status: "printing", can_change_holds: false }));
    render(DetailPage);

    const dialog = await openEditor();
    await userEvent.click(within(dialog).getByRole("button", { name: "Remove" }));

    await vi.waitFor(() =>
      expect(screen.getByText("Status:").parentElement).toHaveTextContent("Printing"),
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("reads a hold change as Filament updated to the requester", async () => {
    signIn(SAM);
    api.getRequest.mockResolvedValue(
      request({ status: "queued", history: [holdsChanged("frank")] }),
    );
    render(DetailPage);

    expect(await screen.findByText("Filament updated by frank")).toBeVisible();
    expect(screen.queryByText(/Holds changed/)).toBeNull();
  });
});
