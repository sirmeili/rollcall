import { render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "#lib/api/client.ts";
import type { HistoryEntry, Move, RequestStatus } from "#lib/api/requests.ts";
import type { Me } from "#lib/api/types.ts";
import { setTimeZone } from "#lib/format.ts";
import { viewport } from "#lib/viewport.svelte.ts";
import { me } from "../test/fixtures.ts";
import { request, row } from "../test/request-fixtures.ts";

const nav = vi.hoisted(() => ({
  page: { params: { id: "41" } as Record<string, string>, url: new URL("https://localhost/") },
  goto: vi.fn(),
}));
vi.mock("$app/state", () => ({ page: nav.page }));
vi.mock("$app/navigation", () => ({ goto: nav.goto }));

const api = vi.hoisted(() => ({
  listRequests: vi.fn(),
  getRequest: vi.fn(),
  moveRequest: vi.fn(),
}));
vi.mock("#lib/api/requests.ts", async (original) => ({
  ...(await original<typeof import("#lib/api/requests.ts")>()),
  ...api,
}));

const { session } = await import("#lib/auth/session.svelte.ts");
const ListPage = (await import("./requests/+page.svelte")).default;
const DetailPage = (await import("./requests/[id]/+page.svelte")).default;

const FRANK = me("admin", { id: 1, username: "frank" });
const DANA = me("editor", { id: 3, username: "dana" });
const SAM = me("viewer", { id: 2, username: "sam", requester: true, has_requests: true });
const VIC = me("viewer", { id: 4, username: "vic" });

const APPROVE_OR_REJECT: Move[] = [
  { to_status: "approved", reason_required: false, photos: false },
  { to_status: "rejected", reason_required: true, photos: false },
];

function signIn(user: Me): void {
  session.user = user;
  session.loaded = true;
}

function moved(to: string, note: string | null): HistoryEntry {
  return {
    kind: "status_changed",
    username: "frank",
    at: "2026-11-18T14:00:00Z",
    fields: null,
    from_value: "submitted",
    to_value: to,
    note,
  };
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"], now: new Date("2026-11-18T15:00:00Z") });
  setTimeZone("UTC");
  viewport().phone = false;
  nav.page.params = { id: "41" };
});
afterEach(() => {
  vi.useRealTimers();
  vi.resetAllMocks();
});

function statusChip(): HTMLElement {
  return screen.getByText("Status:").parentElement!;
}

function actions(): HTMLElement {
  return screen.getByRole("group", { name: "Move this request" });
}

describe("Moving a request", () => {
  it("offers an Admin Approve, as the main step, and Reject", async () => {
    signIn(FRANK);
    api.getRequest.mockResolvedValue(request({ moves: APPROVE_OR_REJECT }));
    render(DetailPage);

    const approve = await screen.findByRole("button", { name: "Approve" });
    const buttons = within(actions()).getAllByRole("button");
    expect(buttons.map((b) => b.textContent?.trim())).toEqual(["Approve", "Reject"]);
    expect(approve).toHaveClass("primary");
    expect(screen.getByRole("button", { name: "Reject" })).not.toHaveClass("primary");
  });

  it.each([
    ["an Editor", DANA],
    ["the Requester", SAM],
    ["a Viewer", VIC],
  ])("offers %s no moves the server doesn't list", async (_who, user) => {
    signIn(user);
    api.getRequest.mockResolvedValue(request({ moves: [] }));
    render(DetailPage);

    await screen.findByRole("heading", { name: "Wingspan insert" });
    expect(screen.queryByRole("group", { name: "Move this request" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Reject" })).toBeNull();
  });

  it("approves with an optional note", async () => {
    signIn(FRANK);
    api.getRequest.mockResolvedValue(request({ moves: APPROVE_OR_REJECT }));
    api.moveRequest.mockResolvedValue(
      request({ status: "approved", history: [moved("approved", "Next week")] }),
    );
    render(DetailPage);

    await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
    const dialog = screen.getByRole("dialog", { name: "Approve this request?" });
    const note = within(dialog).getByLabelText("Note (optional)");
    await userEvent.type(note, "Next week");
    await userEvent.click(within(dialog).getByRole("button", { name: "Approve" }));

    expect(api.moveRequest).toHaveBeenCalledWith(41, "submitted", "approved", "Next week", []);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(statusChip()).toHaveTextContent("Status: Approved");
    expect(await screen.findByText("Approved by frank")).toBeVisible();
    expect(screen.getByText("Next week")).toBeVisible();
  });

  it("asks for a reason before rejecting", async () => {
    signIn(FRANK);
    api.getRequest.mockResolvedValue(request({ moves: APPROVE_OR_REJECT }));
    api.moveRequest.mockResolvedValue(
      request({ status: "rejected", history: [moved("rejected", "No clear PETG.")] }),
    );
    render(DetailPage);

    await userEvent.click(await screen.findByRole("button", { name: "Reject" }));
    const dialog = screen.getByRole("dialog", { name: "Reject this request?" });
    const reason = within(dialog).getByLabelText("Reason");
    const confirm = within(dialog).getByRole("button", { name: "Reject" });
    expect(reason).toBeRequired();
    expect(reason).toHaveAttribute("maxlength", "500");
    expect(dialog).toHaveTextContent("The requester sees the reason.");
    expect(confirm).toBeDisabled();
    await userEvent.type(reason, "   ");
    expect(confirm).toBeDisabled();
    await userEvent.type(reason, "No clear PETG.");
    expect(dialog).toHaveTextContent("17/500");
    await userEvent.click(confirm);

    expect(api.moveRequest).toHaveBeenCalledWith(
      41,
      "submitted",
      "rejected",
      "   No clear PETG.",
      [],
    );
    expect(await screen.findByText("Rejected by frank")).toBeVisible();
    expect(screen.getByText("No clear PETG.")).toBeVisible();
  });

  it("closes the dialog without moving on Cancel or Escape", async () => {
    signIn(FRANK);
    api.getRequest.mockResolvedValue(request({ moves: APPROVE_OR_REJECT }));
    render(DetailPage);

    await userEvent.click(await screen.findByRole("button", { name: "Reject" }));
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" }),
    );
    expect(screen.queryByRole("dialog")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Approve" }));
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Approve" }));
    await userEvent.click(screen.getAllByRole("button", { name: "Cancel" })[0]);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(api.moveRequest).not.toHaveBeenCalled();
  });

  it("keeps Tab inside the dialog", async () => {
    signIn(FRANK);
    api.getRequest.mockResolvedValue(request({ moves: APPROVE_OR_REJECT }));
    render(DetailPage);

    await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
    const dialog = screen.getByRole("dialog");
    const note = within(dialog).getByLabelText("Note (optional)");
    const confirm = within(dialog).getByRole("button", { name: "Approve" });
    expect(note).toHaveFocus();
    await userEvent.tab({ shift: true });
    expect(confirm).toHaveFocus();
    await userEvent.tab();
    expect(note).toHaveFocus();
    await userEvent.tab();
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus();
  });

  it("shows the server's problem with the note in the dialog", async () => {
    signIn(FRANK);
    api.getRequest.mockResolvedValue(request({ moves: APPROVE_OR_REJECT }));
    api.moveRequest.mockRejectedValue(
      new ApiError(422, "refused", { problems: { note: "Give a reason." } }),
    );
    render(DetailPage);

    await userEvent.click(await screen.findByRole("button", { name: "Reject" }));
    const dialog = screen.getByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Reason"), "x");
    await userEvent.click(within(dialog).getByRole("button", { name: "Reject" }));

    expect(await within(dialog).findByText("Give a reason.")).toBeVisible();
  });

  it("explains any other failure in the dialog", async () => {
    signIn(FRANK);
    api.getRequest.mockResolvedValue(request({ moves: APPROVE_OR_REJECT }));
    api.moveRequest.mockRejectedValue(new ApiError(403, "no"));
    render(DetailPage);

    await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
    const dialog = screen.getByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Approve" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Your role cannot do that.");
  });

  it("says when someone else moved it first, and reloads it", async () => {
    signIn(FRANK);
    api.getRequest
      .mockResolvedValueOnce(request({ moves: APPROVE_OR_REJECT }))
      .mockResolvedValueOnce(request({ status: "rejected", moves: [] }));
    api.moveRequest.mockRejectedValue(
      new ApiError(409, "This request has changed. Reload to see it."),
    );
    render(DetailPage);

    await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "Approve" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This request has changed. Reload to see it.",
    );
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(api.getRequest).toHaveBeenCalledTimes(2);
    await vi.waitFor(() => expect(statusChip()).toHaveTextContent("Status: Rejected"));
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  });
});

const OPTIONAL = (...to: RequestStatus[]): Move[] =>
  to.map((to_status) => ({ to_status, reason_required: false, photos: false }));

describe("Moving a request along", () => {
  it.each([
    [
      "approved",
      OPTIONAL("queued", "waiting_on_filament"),
      ["Queue", "Move to Waiting on Filament"],
    ],
    ["waiting_on_filament", OPTIONAL("queued"), ["Queue"]],
    ["queued", OPTIONAL("printing"), ["Start printing"]],
    ["printing", OPTIONAL("done", "failed"), ["Mark Done", "Mark Failed"]],
    ["failed", OPTIONAL("queued"), ["Reprint"]],
    ["done", OPTIONAL("picked_up"), ["Mark Picked Up"]],
  ] as const)(
    "offers an Admin the next steps from %s, the main one first",
    async (status, moves, names) => {
      signIn(FRANK);
      api.getRequest.mockResolvedValue(request({ status, moves: [...moves] }));
      render(DetailPage);

      const main = await screen.findByRole("button", { name: names[0] });
      const buttons = within(actions()).getAllByRole("button");
      expect(buttons.map((b) => b.textContent?.trim())).toEqual(names);
      expect(main).toHaveClass("primary");
      for (const other of buttons.slice(1)) expect(other).not.toHaveClass("primary");
    },
  );

  it("offers the requester Mark Picked Up once it is Done", async () => {
    signIn(SAM);
    api.getRequest.mockResolvedValue(request({ status: "done", moves: OPTIONAL("picked_up") }));
    render(DetailPage);

    const picked = await screen.findByRole("button", { name: "Mark Picked Up" });
    expect(picked).toHaveClass("primary");
    expect(within(actions()).getAllByRole("button")).toHaveLength(1);
  });

  it.each([
    ["Mark Done", "done", "Mark this request Done?"],
    ["Mark Failed", "failed", "Mark this request Failed?"],
  ] as const)("%s asks for an optional note", async (name, to, question) => {
    signIn(FRANK);
    api.getRequest.mockResolvedValue(
      request({ status: "printing", moves: OPTIONAL("done", "failed") }),
    );
    api.moveRequest.mockResolvedValue(request({ status: to }));
    render(DetailPage);

    await userEvent.click(await screen.findByRole("button", { name }));
    const dialog = screen.getByRole("dialog", { name: question });
    const note = within(dialog).getByLabelText("Note (optional)");
    const confirm = within(dialog).getByRole("button", { name });
    expect(note).not.toBeRequired();
    expect(note).toHaveAttribute("maxlength", "500");
    expect(confirm).toBeEnabled();
    await userEvent.click(confirm);

    expect(api.moveRequest).toHaveBeenCalledWith(41, "printing", to, "", []);
    expect(statusChip()).toHaveTextContent(`Status: ${to === "done" ? "Done" : "Failed"}`);
  });

  it("reprints a failed request, and shows the attempt", async () => {
    signIn(FRANK);
    api.getRequest.mockResolvedValue(request({ status: "failed", moves: OPTIONAL("queued") }));
    api.moveRequest.mockResolvedValue(
      request({
        status: "queued",
        attempt: 2,
        history: [{ ...moved("queued", "Bed adhesion."), from_value: "failed" }],
      }),
    );
    render(DetailPage);

    await userEvent.click(await screen.findByRole("button", { name: "Reprint" }));
    const dialog = screen.getByRole("dialog", { name: "Reprint this request?" });
    await userEvent.type(within(dialog).getByLabelText("Note (optional)"), "Bed adhesion.");
    await userEvent.click(within(dialog).getByRole("button", { name: "Reprint" }));

    expect(api.moveRequest).toHaveBeenCalledWith(41, "failed", "queued", "Bed adhesion.", []);
    expect(await screen.findByText("Reprinted by frank")).toBeVisible();
    expect(screen.getByText("Attempt 2")).toBeVisible();
  });
});

describe("Attempt", () => {
  it("is not shown for the first attempt", async () => {
    signIn(SAM);
    api.getRequest.mockResolvedValue(request({ status: "printing", attempt: 1 }));
    render(DetailPage);

    await screen.findByRole("heading", { name: "Wingspan insert" });
    expect(screen.queryByText(/Attempt/)).toBeNull();
  });

  it("shows the attempt under the status badge from the second on", async () => {
    signIn(SAM);
    api.getRequest.mockResolvedValue(request({ status: "printing", attempt: 3 }));
    render(DetailPage);

    expect(await screen.findByText("Attempt 3")).toBeVisible();
  });
});

describe("Cancelling a request", () => {
  const CANCEL_FREELY: Move = { to_status: "cancelled", reason_required: false, photos: false };
  const CANCEL_WITH_REASON: Move = { to_status: "cancelled", reason_required: true, photos: false };

  it.each([
    ["the requester", "queued", SAM, [CANCEL_FREELY], ["Cancel request"]],
    [
      "an Admin",
      "submitted",
      FRANK,
      [...APPROVE_OR_REJECT, CANCEL_WITH_REASON],
      ["Approve", "Reject", "Cancel request"],
    ],
    ["an Admin", "failed", FRANK, [CANCEL_WITH_REASON], ["Cancel request"]],
  ] as const)("offers %s Cancel request in %s", async (_who, status, user, moves, buttons) => {
    signIn(user);
    api.getRequest.mockResolvedValue(request({ status, moves: [...moves] }));
    render(DetailPage);

    const cancel = await screen.findByRole("button", { name: "Cancel request" });
    expect(
      within(actions())
        .getAllByRole("button")
        .map((b) => b.textContent?.trim()),
    ).toEqual(buttons);
    expect(cancel).not.toHaveClass("primary");
  });

  it.each([
    ["an Editor", "submitted", DANA],
    ["the requester", "printing", SAM],
    ["an Admin", "done", FRANK],
    ["the requester", "picked_up", SAM],
  ] as const)(
    "offers %s no Cancel request when the server lists none in %s",
    async (_who, status, user) => {
      signIn(user);
      api.getRequest.mockResolvedValue(request({ status, moves: [] }));
      render(DetailPage);

      await screen.findByRole("heading", { name: "Wingspan insert" });
      expect(screen.queryByRole("button", { name: "Cancel request" })).toBeNull();
    },
  );

  it("lets the requester cancel with an optional note", async () => {
    signIn(SAM);
    api.getRequest.mockResolvedValue(request({ moves: [CANCEL_FREELY] }));
    api.moveRequest.mockResolvedValue(
      request({
        status: "cancelled",
        history: [{ ...moved("cancelled", null), username: "sam" }],
      }),
    );
    render(DetailPage);

    await userEvent.click(await screen.findByRole("button", { name: "Cancel request" }));
    const dialog = screen.getByRole("dialog", { name: "Cancel this request?" });
    const note = within(dialog).getByLabelText("Note (optional)");
    expect(note).not.toBeRequired();
    expect(dialog).toHaveTextContent("Editors and Admins see the note.");
    await userEvent.click(within(dialog).getByRole("button", { name: "Cancel request" }));

    expect(api.moveRequest).toHaveBeenCalledWith(41, "submitted", "cancelled", "", []);
    expect(statusChip()).toHaveTextContent("Status: Cancelled");
    expect(await screen.findByText("Cancelled by sam")).toBeVisible();
  });

  it("asks an Admin for a reason before cancelling someone else's request", async () => {
    signIn(FRANK);
    api.getRequest.mockResolvedValue(request({ status: "failed", moves: [CANCEL_WITH_REASON] }));
    api.moveRequest.mockResolvedValue(request({ status: "cancelled" }));
    render(DetailPage);

    await userEvent.click(await screen.findByRole("button", { name: "Cancel request" }));
    const dialog = screen.getByRole("dialog", { name: "Cancel this request?" });
    const reason = within(dialog).getByLabelText("Reason");
    const confirm = within(dialog).getByRole("button", { name: "Cancel request" });
    expect(reason).toBeRequired();
    expect(dialog).toHaveTextContent("The requester sees the reason.");
    expect(confirm).toBeDisabled();
    await userEvent.type(reason, "The model can't be printed.");
    await userEvent.click(confirm);

    expect(api.moveRequest).toHaveBeenCalledWith(
      41,
      "failed",
      "cancelled",
      "The model can't be printed.",
      [],
    );
  });

  it("keeps the request when the dialog is closed", async () => {
    signIn(SAM);
    api.getRequest.mockResolvedValue(request({ moves: [CANCEL_FREELY] }));
    render(DetailPage);

    await userEvent.click(await screen.findByRole("button", { name: "Cancel request" }));
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "Keep request" }),
    );

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(api.moveRequest).not.toHaveBeenCalled();
  });
});

describe("Status badge", () => {
  it("names the status on the list", async () => {
    signIn(DANA);
    api.listRequests.mockResolvedValue([
      row({ id: 1, title: "One", status: "approved" }),
      row({ id: 2, title: "Two", status: "waiting_on_filament" }),
    ]);
    render(ListPage);

    const rows = await screen.findAllByRole("row");
    expect(rows[1]).toHaveTextContent("Status: Approved");
    expect(rows[2]).toHaveTextContent("Status: Waiting on Filament");
  });

  it("names the status on the detail page", async () => {
    signIn(SAM);
    api.getRequest.mockResolvedValue(request({ status: "rejected" }));
    render(DetailPage);

    await screen.findByRole("heading", { name: "Wingspan insert" });
    expect(statusChip()).toHaveTextContent("Status: Rejected");
    expect(statusChip()).toHaveClass("tagchip", "st-rejected");
  });
});
