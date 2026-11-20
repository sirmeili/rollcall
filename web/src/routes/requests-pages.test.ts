import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Catalog, CatalogColor } from "#lib/api/catalog.ts";
import { ApiError } from "#lib/api/client.ts";
import type { Choice, PrintRequest, RequestRow, Upload } from "#lib/api/requests.ts";
import type { Me } from "#lib/api/types.ts";
import { setTimeZone } from "#lib/format.ts";
import { viewport } from "#lib/viewport.svelte.ts";
import { me, product, summary } from "../test/fixtures.ts";
import { choice, request, row } from "../test/request-fixtures.ts";

const nav = vi.hoisted(() => ({
  page: { params: { id: "41" } as Record<string, string>, url: new URL("https://localhost/") },
  goto: vi.fn(),
}));
vi.mock("$app/state", () => ({ page: nav.page }));
vi.mock("$app/navigation", () => ({ goto: nav.goto }));

const api = vi.hoisted(() => ({
  listRequests: vi.fn(),
  getRequest: vi.fn(),
  submitRequest: vi.fn(),
  editRequest: vi.fn(),
  changePriority: vi.fn(),
  uploadModel: vi.fn(),
}));
vi.mock("#lib/api/requests.ts", async (original) => ({
  ...(await original<typeof import("#lib/api/requests.ts")>()),
  ...api,
}));

const stock = vi.hoisted(() => ({ getInventory: vi.fn() }));
vi.mock("#lib/api/stock.ts", () => stock);
const catalogApi = vi.hoisted(() => ({ getCatalog: vi.fn() }));
vi.mock("#lib/api/catalog.ts", () => catalogApi);

const { session } = await import("#lib/auth/session.svelte.ts");
const ListPage = (await import("./requests/+page.svelte")).default;
const NewPage = (await import("./requests/new/+page.svelte")).default;
const DetailPage = (await import("./requests/[id]/+page.svelte")).default;
const EditPage = (await import("./requests/[id]/edit/+page.svelte")).default;

const SAM = me("viewer", { id: 2, username: "sam", requester: true, has_requests: true });
const DANA = me("editor", { id: 3, username: "dana" });

function signIn(user: Me): void {
  session.user = user;
  session.loaded = true;
}

function color(name: string, fields: Partial<CatalogColor> = {}): CatalogColor {
  return {
    uuid: name.toLowerCase().replace(/ /g, "-"),
    name,
    hexes: ["FF69B4"],
    discontinued: false,
    multi_color: false,
    gradient: false,
    bambu_code: null,
    similar: [],
    owned: false,
    owned_products: [],
    linked_none_in_stock: [],
    ...fields,
  };
}

const CATALOG: Catalog = {
  lines: [
    {
      uuid: "pla-basic",
      name: "PLA Basic",
      material: "PLA",
      colors: [color("Hot Pink"), color("Jade White", { owned: true })],
    },
  ],
  synced: true,
  dataset_version: "1",
  last_success_at: null,
  cutoff: 10,
  out_of_date: false,
  store_address: "https://store.example",
};

const BLUE = summary({
  product: product({ id: 7, display_name: "Blue PLA", color_rgba: "0A2CA5FF" }),
  counts: { sealed: 2, open: 1, empty: 0, unknown: 0 },
});

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"], now: new Date("2026-11-18T15:00:00Z") });
  setTimeZone("UTC");
  signIn(SAM);
  viewport().phone = false;
  stock.getInventory.mockResolvedValue([BLUE]);
  catalogApi.getCatalog.mockResolvedValue(CATALOG);
  nav.page.params = { id: "41" };
});
afterEach(() => {
  vi.useRealTimers();
  vi.resetAllMocks();
});

describe("Requests list", () => {
  it("shows Editors every request with who asked, most urgent first", async () => {
    signIn(DANA);
    api.listRequests.mockResolvedValue([
      row(),
      row({ id: 42, title: "Lamp", priority: "no_rush", needed_by: null, model: "notes" }),
    ]);
    render(ListPage);

    expect(
      await screen.findByText("Print requests from everyone. Most urgent first."),
    ).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "Requester" })).toBeInTheDocument();
    expect(screen.getByText(/requests? · Most urgent first/)).toHaveTextContent(
      "2 requests · Most urgent first, then by needed-by date, then oldest first",
    );
    const rows = screen.getAllByRole("row").slice(1);
    expect(within(rows[0]).getByRole("link", { name: "Wingspan insert" })).toHaveAttribute(
      "href",
      "/requests/41",
    );
    expect(rows[0]).toHaveTextContent("Priority: Urgent");
    expect(rows[0]).toHaveTextContent("File and link");
    expect(rows[0]).toHaveTextContent("in 3 days");
    expect(rows[0]).toHaveTextContent("2 days ago");
    expect(rows[0]).toHaveTextContent("Filament: Blue PLA, Hot Pink PLA Basic");
    expect(rows[1]).toHaveTextContent("No date");
    expect(rows[1]).toHaveTextContent("Notes only");
    expect(screen.queryByRole("link", { name: "New request" })).toBeNull();
  });

  it("shows a Requester their own requests and New request", async () => {
    api.listRequests.mockResolvedValue([row()]);
    render(ListPage);

    expect(
      await screen.findByText(
        "Your print requests. You can edit a request while it's still Submitted.",
      ),
    ).toBeVisible();
    expect(screen.queryByRole("columnheader", { name: "Requester" })).toBeNull();
    expect(screen.getByRole("link", { name: "New request" })).toHaveAttribute(
      "href",
      "/requests/new",
    );
    expect(screen.getByText(/requests? · Most urgent first/)).toHaveTextContent("1 request ·");
  });

  it("lets a former Requester open their earlier requests", async () => {
    signIn({ ...SAM, requester: false });
    api.listRequests.mockResolvedValue([row()]);
    render(ListPage);

    expect(await screen.findByText(/Your earlier print requests/)).toBeVisible();
    expect(screen.queryByRole("link", { name: "New request" })).toBeNull();
  });

  it.each([
    [DANA, "No print requests yet", false],
    [{ ...DANA, requester: true }, "No print requests yet", true],
    [SAM, "You haven't asked for any prints yet", true],
    [{ ...SAM, requester: false }, "You don't have any print requests", false],
  ])("explains an empty list (%#)", async (user, heading, canNew) => {
    signIn(user);
    api.listRequests.mockResolvedValue([]);
    render(ListPage);

    expect(await screen.findByRole("heading", { name: heading })).toBeVisible();
    expect(screen.queryAllByRole("link", { name: "New request" })).toHaveLength(canNew ? 2 : 0);
  });

  it("shows cards on a phone", async () => {
    signIn(DANA);
    viewport().phone = true;
    api.listRequests.mockResolvedValue([row({ needed_by: null })]);
    render(ListPage);

    const card = (await screen.findByRole("link", { name: "Wingspan insert" })).closest("li")!;
    expect(screen.queryByRole("table")).toBeNull();
    expect(card).toHaveTextContent("Requester: sam");
    expect(card).toHaveTextContent("Submitted 2 days ago");
    expect(card).toHaveTextContent("No needed-by date");
  });

  it("shows a card's needed-by date and the first four filaments", async () => {
    viewport().phone = true;
    const ring = { name: "Blue PLA", hexes: ["0A2CA5"] };
    api.listRequests.mockResolvedValue([row({ choices: [ring, ring, ring, ring, ring, ring] })]);
    render(ListPage);

    const card = (await screen.findByRole("link", { name: "Wingspan insert" })).closest("li")!;
    expect(card).toHaveTextContent("Needed by Nov 21 · in 3 days");
    expect(card).toHaveTextContent("+2");
  });

  it("leaves out who asked on a Requester's phone", async () => {
    viewport().phone = true;
    api.listRequests.mockResolvedValue([row()]);
    render(ListPage);

    const card = (await screen.findByRole("link", { name: "Wingspan insert" })).closest("li")!;
    expect(card).not.toHaveTextContent("Requester:");
  });

  it("says when the list can't load", async () => {
    api.listRequests.mockRejectedValue(new ApiError(0, "down"));
    render(ListPage);

    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server.");
  });
});

describe("Request detail", () => {
  it("shows the model, filament, notes, facts and history", async () => {
    api.getRequest.mockResolvedValue(request());
    render(DetailPage);

    expect(await screen.findByRole("heading", { name: "Wingspan insert" })).toBeVisible();
    expect(api.getRequest).toHaveBeenCalledWith(41);
    expect(screen.getByText("Requested by sam · submitted 2 days ago")).toBeVisible();
    expect(screen.getByRole("link", { name: "Download wingspan.3mf" })).toHaveAttribute(
      "href",
      expect.stringMatching(/\/requests\/41\/file$/),
    );
    expect(screen.getByText("3MF · 18.6 MB")).toBeVisible();
    const open = screen.getByRole("link", { name: "Open link" });
    expect(open).toHaveAttribute("href", "https://makerworld.com/models/412877");
    expect(open).toHaveAttribute("target", "_blank");
    expect(open).toHaveAttribute("rel", "noopener noreferrer");

    const [blue, pink] = within(
      screen.getByRole("list", { name: "Filament choices, in order" }),
    ).getAllByRole("listitem");
    expect(blue).toHaveTextContent("Choice 1: Blue PLA");
    expect(blue).toHaveTextContent("PLA · 2 sealed · 1 open");
    expect(blue).toHaveTextContent("“main body”");
    expect(within(blue).queryByRole("link", { name: /Find in store/ })).toBeNull();
    expect(pink).toHaveTextContent("Similar in stock: Magenta PLA");
    expect(pink).toHaveTextContent("No note");
    expect(within(pink).getByRole("link", { name: /Find in store/ })).toHaveAttribute(
      "href",
      "https://store.example/search?q=PLA%20Basic%20Hot%20Pink",
    );

    expect(screen.getByText("The version with the egg tray.")).toBeVisible();
    const history = screen.getByRole("heading", { name: "History" }).closest("section")!;
    expect(history).toHaveTextContent("Priority changed by dana");
    expect(history).toHaveTextContent("Urgent → Normal");
    expect(history).toHaveTextContent("Edited by sam");
    expect(history).toHaveTextContent("Changed notes and needed by");
    expect(history).toHaveTextContent(/Submitted by sam\s*From the shared folder/);
    const facts = screen.getByRole("complementary", { name: "Request details" });
    expect(facts).toHaveTextContent("Needed by Nov 21 in 3 days");
    expect(screen.queryByRole("link", { name: "Edit" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Change priority" })).toBeNull();
  });

  it("says when the file is missing, and when a color has left the catalog", async () => {
    api.getRequest.mockResolvedValue(
      request({
        file: { name: "wingspan.3mf", size: 10, kind: "3mf", missing: true },
        link: null,
        choices: [
          choice({ in_catalog: false }),
          choice({ name: "Rainbow PLA Basic", multi_color: true, bambu_code: "10900" }),
        ],
      }),
    );
    render(DetailPage);

    expect(await screen.findByText("File missing")).toBeVisible();
    expect(screen.queryByRole("link", { name: /Download/ })).toBeNull();
    const [gone, rainbow] = within(
      screen.getByRole("list", { name: "Filament choices, in order" }),
    ).getAllByRole("listitem");
    expect(gone).toHaveTextContent("No longer in the catalog");
    expect(within(gone).queryByRole("link", { name: /Find in store/ })).toBeNull();
    expect(rainbow).toHaveTextContent("PLA · 10900 · not in stock");
    expect(rainbow).toHaveTextContent("Multi-color: no comparison");
    expect(within(rainbow).getByRole("link", { name: /Find in store/ })).toHaveAttribute(
      "href",
      "https://store.example/search?q=10900",
    );
  });

  it("says when a chosen product has none left", async () => {
    api.getRequest.mockResolvedValue(
      request({
        choices: [
          choice({
            kind: "product",
            name: "Blue PLA",
            material: null,
            product_id: 7,
            sealed: 0,
            open: 0,
          }),
          choice({ line: null, color_name: null, name: "Mystery", bambu_code: null }),
        ],
      }),
    );
    render(DetailPage);

    const [blue, mystery] = within(
      await screen.findByRole("list", { name: "Filament choices, in order" }),
    ).getAllByRole("listitem");
    expect(blue).toHaveTextContent("Owned none left");
    expect(within(mystery).getByRole("link", { name: /Find in store/ })).toHaveAttribute(
      "href",
      "https://store.example/search?q=%20Mystery",
    );
  });

  it("says when the notes are where the model is", async () => {
    api.getRequest.mockResolvedValue(request({ file: null, link: null, notes: "" }));
    render(DetailPage);

    expect(
      await screen.findByText("No file or link. The notes say where the model is."),
    ).toBeVisible();
    expect(screen.getByText("No notes.")).toBeVisible();
  });

  it("offers Edit to the Requester who can edit", async () => {
    api.getRequest.mockResolvedValue(request({ can_edit: true }));
    render(DetailPage);

    expect(await screen.findByRole("link", { name: "Edit" })).toHaveAttribute(
      "href",
      "/requests/41/edit",
    );
  });

  it("tells a former Requester why there is no Edit", async () => {
    signIn({ ...SAM, requester: false });
    api.getRequest.mockResolvedValue(request());
    render(DetailPage);

    expect(
      await screen.findByText("You can no longer edit this request: you're no longer a Requester."),
    ).toBeVisible();
    expect(screen.queryByRole("link", { name: "Edit" })).toBeNull();
  });

  it("lets an Editor change the priority", async () => {
    signIn(DANA);
    api.getRequest.mockResolvedValue(request({ can_change_priority: true }));
    api.changePriority.mockResolvedValue(
      request({ priority: "urgent", can_change_priority: true }),
    );
    render(DetailPage);

    const change = await screen.findByRole("button", { name: "Change priority" });
    expect(change).toBeDisabled();
    await userEvent.click(screen.getByRole("radio", { name: "Urgent" }));
    await userEvent.click(change);

    expect(api.changePriority).toHaveBeenCalledWith(41, "urgent");
    expect(await screen.findByText("Changed from Normal to Urgent.")).toBeVisible();
    expect(screen.getAllByText("Urgent").length).toBeGreaterThan(1);
  });

  it("explains a failed priority change", async () => {
    signIn(DANA);
    api.getRequest.mockResolvedValue(request({ can_change_priority: true }));
    api.changePriority.mockRejectedValue(new ApiError(403, "no"));
    render(DetailPage);

    await userEvent.click(await screen.findByRole("radio", { name: "No rush" }));
    await userEvent.click(screen.getByRole("button", { name: "Change priority" }));

    expect(await screen.findByText("Your role cannot do that.")).toBeVisible();
  });

  it.each([
    ["abc", null],
    ["41", new ApiError(404, "no")],
  ])("says a request it can't show is not found (%s)", async (id, error) => {
    nav.page.params = { id };
    api.getRequest.mockRejectedValue(error);
    render(DetailPage);

    expect(await screen.findByRole("alert")).toHaveTextContent("Not found.");
  });
});

function upload(fields: Partial<Upload> = {}): Upload {
  return { id: "u1", name: "dragon.3mf", size: 3, kind: "3mf", ...fields };
}

/** A fake upload the test finishes, fails or watches being cancelled. */
function fakeUpload() {
  let finish!: (done: Upload) => void;
  let fail!: (error: Error) => void;
  let progress!: (percent: number) => void;
  const cancel = vi.fn();
  api.uploadModel.mockImplementation((_file: File, onprogress: (percent: number) => void) => {
    progress = onprogress;
    return {
      done: new Promise<Upload>((resolve, reject) => {
        finish = resolve;
        fail = reject;
      }),
      cancel,
    };
  });
  return {
    finish: (done: Upload) => finish(done),
    fail: (error: Error) => fail(error),
    progress: (percent: number) => progress(percent),
    cancel,
  };
}

function modelFile(name = "dragon.3mf", size = 3): File {
  const file = new File(["abc"], name);
  Object.defineProperty(file, "size", { value: size });
  return file;
}

async function pickFile(file: File): Promise<void> {
  await fireEvent.change(screen.getByLabelText("Model file"), { target: { files: [file] } });
}

async function addFilament(search: string, name: string): Promise<void> {
  const box = screen.getByLabelText("Add filament");
  await userEvent.clear(box);
  await userEvent.type(box, search);
  await userEvent.click(screen.getByRole("button", { name: `Add ${name}` }));
}

describe("New request", () => {
  it("is only for Requesters", () => {
    signIn(DANA);
    render(NewPage);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "You can no longer submit or edit print requests.",
    );
    expect(stock.getInventory).not.toHaveBeenCalled();
  });

  it("lists every problem before sending", async () => {
    render(NewPage);

    await userEvent.click(await screen.findByRole("button", { name: "Submit request" }));

    const summary = screen.getByRole("alert");
    expect(summary).toHaveTextContent("Fix 3 things before submitting");
    expect(summary).toHaveTextContent("Enter a title.");
    expect(summary).toHaveTextContent(
      "Add a file or a link, or say in the notes where the model is.",
    );
    expect(summary).toHaveTextContent("Add at least one filament.");
    expect(summary).toHaveFocus();
    expect(screen.getByLabelText("Title")).toHaveAttribute("aria-invalid", "true");
    expect(api.submitRequest).not.toHaveBeenCalled();

    await userEvent.click(within(summary).getByRole("link", { name: "Enter a title." }));
    expect(screen.getByLabelText("Title")).toHaveFocus();
    await userEvent.type(screen.getByLabelText("Title"), "Dragon");
    expect(screen.getByRole("alert")).toHaveTextContent("Fix 2 things before submitting");
  });

  it("submits the request and opens it", async () => {
    api.submitRequest.mockResolvedValue(request({ id: 43 }));
    render(NewPage);

    await userEvent.type(await screen.findByLabelText("Title"), " Wingspan insert ");
    await userEvent.click(screen.getByRole("button", { name: "One more" }));
    await userEvent.click(screen.getByRole("radio", { name: "Urgent" }));
    await fireEvent.input(screen.getByLabelText(/Needed by/), { target: { value: "2026-12-05" } });
    await userEvent.type(screen.getByLabelText(/Link/), "https://makerworld.com/m/1");
    expect(screen.getByRole("textbox", { name: /^Notes/ })).toHaveAccessibleName(
      "Notes (optional)",
    );
    await userEvent.click(screen.getByRole("button", { name: "Add Blue PLA" }));
    await addFilament("pink", "Hot Pink PLA Basic");
    await userEvent.type(screen.getByLabelText("Note for Blue PLA"), "body");
    await userEvent.click(screen.getByRole("button", { name: "Submit request" }));

    expect(api.submitRequest).toHaveBeenCalledWith({
      title: "Wingspan insert",
      notes: "",
      quantity: 2,
      needed_by: "2026-12-05",
      priority: "urgent",
      link: "https://makerworld.com/m/1",
      choices: [
        { product_id: 7, note: "body" },
        { catalog_color: "hot-pink", note: "" },
      ],
      upload_id: null,
    });
    await waitFor(() => expect(nav.goto).toHaveBeenCalledWith("/requests/43"));
  });

  it("offers in-stock products and catalog colors no one has", async () => {
    render(NewPage);

    expect(
      await screen.findByText(
        "Showing 1 of your 1 products. Type to search all of them and the catalog.",
      ),
    ).toBeVisible();
    await userEvent.type(screen.getByLabelText("Add filament"), "pla");
    expect(screen.getByText("Your products · in stock")).toBeVisible();
    expect(screen.getByText("Catalog colors · not in stock")).toBeVisible();
    expect(screen.queryByRole("button", { name: /Jade White/ })).toBeNull();
    expect(screen.getByText("1 of your products, 1 catalog color")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Add Blue PLA" }));
    expect(screen.getByRole("button", { name: "Added Blue PLA" })).toBeDisabled();
  });

  it("shows each choice's stock or similar colors in the picker", async () => {
    catalogApi.getCatalog.mockResolvedValue({
      ...CATALOG,
      lines: [
        {
          ...CATALOG.lines[0],
          colors: [
            color("Hot Pink"),
            color("Rainbow", { multi_color: true, hexes: ["FF0000", "00FF00"] }),
            color("Sky Blue", {
              similar: [
                {
                  product_id: 7,
                  name: "Blue PLA",
                  hex: "0A2CA5",
                  material: "PLA",
                  delta_e: 3,
                  sealed: 2,
                  open: 1,
                  different_material: false,
                },
              ],
            }),
          ],
        },
      ],
    });
    render(NewPage);
    await userEvent.type(await screen.findByLabelText("Add filament"), "pla");

    const sub = (name: string) => screen.getByRole("button", { name: `Add ${name}` }).textContent;
    expect(sub("Blue PLA")).toContain("PLA · 2 sealed · 1 open");
    expect(sub("Hot Pink PLA Basic")).toContain("No similar color in stock");
    expect(sub("Rainbow PLA Basic")).toContain("Multi-color: no comparison");
    expect(sub("Sky Blue PLA Basic")).toContain("Similar in stock: Blue PLA");
  });

  it("orders and removes choices", async () => {
    render(NewPage);
    await screen.findByLabelText("Add filament");
    await userEvent.click(screen.getByRole("button", { name: "Add Blue PLA" }));
    await addFilament("pink", "Hot Pink PLA Basic");

    const choices = () =>
      within(screen.getByRole("list", { name: "Filament choices, in order" }))
        .getAllByRole("listitem")
        .map((li) => li.querySelector(".cname")?.textContent);
    expect(screen.getByRole("button", { name: "Move Blue PLA up" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Move Blue PLA down" }));
    expect(choices()).toEqual(["Choice 1: Hot Pink PLA Basic", "Choice 2: Blue PLA"]);
    await userEvent.click(screen.getByRole("button", { name: "Move Blue PLA up" }));
    expect(choices()).toEqual(["Choice 1: Blue PLA", "Choice 2: Hot Pink PLA Basic"]);
    await userEvent.click(screen.getByRole("button", { name: "Remove Blue PLA" }));
    expect(choices()).toEqual(["Choice 1: Hot Pink PLA Basic"]);
  });

  it("offers Find in store on a chosen catalog color, not on a product", async () => {
    render(NewPage);
    await screen.findByLabelText("Add filament");
    await userEvent.click(screen.getByRole("button", { name: "Add Blue PLA" }));
    await addFilament("pink", "Hot Pink PLA Basic");

    const [blue, pink] = within(
      screen.getByRole("list", { name: "Filament choices, in order" }),
    ).getAllByRole("listitem");
    expect(within(blue).queryByRole("link", { name: /Find in store/ })).toBeNull();
    expect(within(pink).getByRole("link", { name: /Find in store/ })).toHaveAttribute(
      "href",
      "https://store.example/search?q=PLA%20Basic%20Hot%20Pink",
    );
  });

  it("still offers products when the catalog can't load", async () => {
    catalogApi.getCatalog.mockRejectedValue(new ApiError(0, "down"));
    render(NewPage);

    expect(
      await screen.findByText("Some filament couldn't be loaded: Cannot reach the server."),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Add Blue PLA" })).toBeVisible();
  });

  it("uploads a model file and sends it with the request", async () => {
    const sent = fakeUpload();
    api.submitRequest.mockResolvedValue(request({ id: 43 }));
    render(NewPage);
    await userEvent.type(await screen.findByLabelText("Title"), "Dragon");
    await userEvent.click(screen.getByRole("button", { name: "Add Blue PLA" }));

    await pickFile(modelFile("dragon.3mf", 54_840_115));
    sent.progress(38);
    expect(
      await screen.findByRole("progressbar", { name: "Uploading dragon.3mf" }),
    ).toHaveAttribute("aria-valuenow", "38");
    expect(screen.getByText("Uploading… 38% · 52.3 MB")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Submit request" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "dragon.3mf is still uploading. Wait for it to finish, or cancel it.",
    );

    sent.finish(upload({ size: 54_840_115 }));
    expect(await screen.findByText("52.3 MB · uploaded")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Submit request" }));

    expect(api.submitRequest).toHaveBeenCalledWith(expect.objectContaining({ upload_id: "u1" }));
  });

  it("checks the file type and size before uploading", async () => {
    render(NewPage);
    await screen.findByLabelText("Title");

    await pickFile(modelFile("phone-stand.obj"));
    expect(
      screen.getByText("phone-stand.obj isn't a 3MF or STL file. Choose a .3mf or .stl file."),
    ).toBeVisible();
    await pickFile(modelFile("plate.3mf", 138_832_691));
    expect(screen.getByText("plate.3mf is 132.4 MB. Files can be up to 95 MB.")).toBeVisible();
    expect(api.uploadModel).not.toHaveBeenCalled();
  });

  it("cancels an upload", async () => {
    const sent = fakeUpload();
    render(NewPage);
    await screen.findByLabelText("Title");

    await pickFile(modelFile());
    await userEvent.click(
      await screen.findByRole("button", { name: "Cancel uploading dragon.3mf" }),
    );

    expect(sent.cancel).toHaveBeenCalled();
    expect(screen.getByText("Drag a 3MF or STL file here")).toBeVisible();
  });

  it("ignores an upload that ends after it was cancelled, and an empty pick", async () => {
    const sent = fakeUpload();
    render(NewPage);
    await screen.findByLabelText("Title");

    await fireEvent.change(screen.getByLabelText("Model file"), { target: { files: [] } });
    expect(api.uploadModel).not.toHaveBeenCalled();
    await pickFile(modelFile());
    sent.progress(10);
    await userEvent.click(
      await screen.findByRole("button", { name: "Cancel uploading dragon.3mf" }),
    );
    sent.progress(20);
    sent.fail(new ApiError(0, "Upload cancelled"));
    await Promise.resolve();

    expect(screen.getByText("Drag a 3MF or STL file here")).toBeVisible();
    expect(screen.queryByText(/Upload failed/)).toBeNull();
  });

  it("ignores a finished upload that was cancelled", async () => {
    const sent = fakeUpload();
    render(NewPage);
    await screen.findByLabelText("Title");

    await pickFile(modelFile());
    await userEvent.click(
      await screen.findByRole("button", { name: "Cancel uploading dragon.3mf" }),
    );
    sent.finish(upload());
    await Promise.resolve();

    expect(screen.getByText("Drag a 3MF or STL file here")).toBeVisible();
  });

  it("retries or removes a failed upload", async () => {
    const sent = fakeUpload();
    render(NewPage);
    await screen.findByLabelText("Title");

    await pickFile(modelFile());
    sent.progress(61);
    sent.fail(new ApiError(0, "The connection dropped"));
    expect(await screen.findByText("Upload failed at 61%: Cannot reach the server.")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Try uploading dragon.3mf again" }));
    expect(api.uploadModel).toHaveBeenCalledTimes(2);
    sent.fail(new ApiError(422, "That isn't a 3MF or STL file."));
    await userEvent.click(await screen.findByRole("button", { name: "Remove dragon.3mf" }));
    expect(screen.getByText("Drag a 3MF or STL file here")).toBeVisible();
  });

  it("shows the problems the server finds", async () => {
    api.submitRequest.mockRejectedValue(
      new ApiError(422, "refused", {
        problems: { choices: "Pick products with a Sealed or Open spool, or a catalog color." },
      }),
    );
    render(NewPage);
    await userEvent.type(await screen.findByLabelText("Title"), "Dragon");
    await userEvent.type(screen.getByRole("textbox", { name: /^Notes/ }), "On the USB stick");
    await userEvent.click(screen.getByRole("button", { name: "Add Blue PLA" }));
    await userEvent.click(screen.getByRole("button", { name: "Submit request" }));

    const summary = await screen.findByRole("alert");
    expect(summary).toHaveTextContent("Fix 1 thing before submitting");
    expect(summary).toHaveTextContent("Pick products with a Sealed or Open spool");
  });

  it("explains a failure that isn't about the fields", async () => {
    api.submitRequest.mockRejectedValue(new ApiError(403, "no"));
    render(NewPage);
    await userEvent.type(await screen.findByLabelText("Title"), "Dragon");
    await userEvent.type(screen.getByRole("textbox", { name: /^Notes/ }), "On the USB stick");
    await userEvent.click(screen.getByRole("button", { name: "Add Blue PLA" }));
    await userEvent.click(screen.getByRole("button", { name: "Submit request" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Your role cannot do that.");
  });

  it("makes the notes required when there is no file or link", async () => {
    render(NewPage);

    expect(await screen.findByRole("textbox", { name: /^Notes/ })).toHaveAccessibleName(
      "Notes (required: say where the model is)",
    );
    expect(
      screen.getByText("No file or link? Then say in the notes where the model is."),
    ).toBeVisible();
  });

  it("shows each field's problem beside it", async () => {
    render(NewPage);
    await userEvent.type(await screen.findByLabelText("Title"), "Dragon");
    await userEvent.clear(screen.getByLabelText("Quantity"));
    await userEvent.type(screen.getByLabelText("Quantity"), "0");
    await fireEvent.input(screen.getByLabelText(/Needed by/), { target: { value: "2026-11-01" } });
    await userEvent.type(screen.getByLabelText(/Link/), "makerworld.com");
    await userEvent.click(screen.getByRole("button", { name: "Submit request" }));

    for (const [label, message] of [
      ["Quantity", "Enter a quantity from 1 to 100."],
      [/Needed by/, "Needed by can't be in the past. Pick today or later, or leave it empty."],
      [/Link/, "Enter a link that starts with http:// or https://."],
    ] as const) {
      expect(screen.getByLabelText(label)).toHaveAttribute("aria-invalid", "true");
      expect(screen.getAllByText(message)).toHaveLength(2);
    }
    await userEvent.click(screen.getByRole("link", { name: "Add at least one filament." }));
    expect(screen.getByLabelText("Add filament")).toHaveFocus();
  });

  it("takes a dropped file and replaces it", async () => {
    const sent = fakeUpload();
    render(NewPage);
    await screen.findByLabelText("Title");
    const zone = screen.getByText("Drag a 3MF or STL file here").parentElement!;

    await fireEvent.dragOver(zone);
    expect(zone).toHaveClass("over");
    await fireEvent.dragLeave(zone);
    expect(zone).not.toHaveClass("over");
    await fireEvent.drop(zone, { dataTransfer: { files: [modelFile("first.stl")] } });
    sent.finish(upload({ name: "first.stl" }));
    const replace = await screen.findByRole("button", { name: "Replace first.stl" });

    const click = vi.spyOn(HTMLInputElement.prototype, "click").mockImplementation(() => {});
    await userEvent.click(replace);
    expect(click).toHaveBeenCalled();
    click.mockRestore();
    await pickFile(modelFile("second.stl"));
    expect(api.uploadModel).toHaveBeenCalledTimes(2);
  });

  it("steps the quantity between 1 and 100", async () => {
    render(NewPage);
    const quantity = await screen.findByLabelText("Quantity");

    await userEvent.click(screen.getByRole("button", { name: "One fewer" }));
    expect(quantity).toHaveValue("1");
    await userEvent.clear(quantity);
    await userEvent.type(quantity, "100");
    await userEvent.click(screen.getByRole("button", { name: "One more" }));
    expect(quantity).toHaveValue("100");
    await userEvent.clear(quantity);
    await userEvent.click(screen.getByRole("button", { name: "One more" }));
    expect(quantity).toHaveValue("1");
  });
});

describe("Edit request", () => {
  it("starts from the request and saves the changes", async () => {
    api.getRequest.mockResolvedValue(request({ can_edit: true }));
    api.editRequest.mockResolvedValue(request());
    render(EditPage);

    const title = await screen.findByLabelText("Title");
    expect(title).toHaveValue("Wingspan insert");
    expect(screen.getByRole("heading", { name: "Edit request" })).toBeVisible();
    expect(screen.getByText("18.6 MB · uploaded")).toBeVisible();
    expect(screen.getByLabelText("Note for Blue PLA")).toHaveValue("main body");
    await userEvent.type(title, " v2");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(api.editRequest).toHaveBeenCalledWith(
      41,
      expect.objectContaining({
        title: "Wingspan insert v2",
        upload_id: null,
        remove_file: false,
        choices: [
          { product_id: 7, note: "main body" },
          { catalog_color: "hot-pink", note: "" },
        ],
      }),
    );
    await waitFor(() => expect(nav.goto).toHaveBeenCalledWith("/requests/41"));
  });

  it("offers Find in store on a saved catalog color, unless it has left the catalog", async () => {
    api.getRequest.mockResolvedValue(
      request({
        can_edit: true,
        store_address: "https://eu.store.example",
        choices: [
          ...request().choices,
          choice({ catalog_color: "old", name: "Old Gold PLA Basic", in_catalog: false }),
        ],
      }),
    );
    render(EditPage);
    await screen.findByLabelText("Title");

    const [blue, pink, gone] = within(
      screen.getByRole("list", { name: "Filament choices, in order" }),
    ).getAllByRole("listitem");
    expect(within(blue).queryByRole("link", { name: /Find in store/ })).toBeNull();
    expect(within(pink).getByRole("link", { name: /Find in store/ })).toHaveAttribute(
      "href",
      "https://eu.store.example/search?q=PLA%20Basic%20Hot%20Pink",
    );
    expect(gone).toHaveTextContent("No longer in the catalog");
    expect(within(gone).queryByRole("link", { name: /Find in store/ })).toBeNull();
  });

  it("adds no more filament once it has 20", async () => {
    const twenty = Array.from({ length: 20 }, (_, i) =>
      choice({ catalog_color: `c${i}`, name: `Color ${i}` }),
    );
    api.getRequest.mockResolvedValue(request({ can_edit: true, choices: twenty }));
    render(EditPage);

    await userEvent.type(await screen.findByLabelText("Add filament"), "pla");

    expect(screen.getByText("A request can have up to 20 filaments.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Add Blue PLA" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Add Hot Pink PLA Basic" })).toBeDisabled();
  });

  it("removes the file", async () => {
    api.getRequest.mockResolvedValue(request({ can_edit: true }));
    api.editRequest.mockResolvedValue(request());
    render(EditPage);

    await userEvent.click(await screen.findByRole("button", { name: "Remove wingspan.3mf" }));
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(api.editRequest).toHaveBeenCalledWith(
      41,
      expect.objectContaining({ remove_file: true }),
    );
  });

  it("asks for a new needed-by date once it has passed", async () => {
    api.getRequest.mockResolvedValue(request({ can_edit: true, needed_by: "2026-11-10" }));
    render(EditPage);

    await userEvent.click(await screen.findByRole("button", { name: "Save changes" }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Needed by can't be in the past. Pick today or later, or leave it empty.",
    );
    expect(api.editRequest).not.toHaveBeenCalled();
  });

  it("shows a file missing from disk and takes a new one", async () => {
    const sent = fakeUpload();
    api.getRequest.mockResolvedValue(
      request({
        can_edit: true,
        link: null,
        file: { name: "wingspan.3mf", size: 10, kind: "3mf", missing: true },
      }),
    );
    api.editRequest.mockResolvedValue(request());
    render(EditPage);

    expect(await screen.findByText("File missing")).toBeVisible();
    expect(screen.getByRole("textbox", { name: /^Notes/ })).toHaveAccessibleName(
      "Notes (required: say where the model is)",
    );
    await pickFile(modelFile("wingspan.3mf"));
    sent.finish(upload({ name: "wingspan.3mf" }));
    await screen.findByText("1 KB · uploaded");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(api.editRequest).toHaveBeenCalledWith(41, expect.objectContaining({ upload_id: "u1" }));
  });

  it("tells a former Requester why they can't edit", async () => {
    signIn({ ...SAM, requester: false });
    api.getRequest.mockResolvedValue(request({ can_edit: false }));
    render(EditPage);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "You can no longer edit this request: you're no longer a Requester.",
    );
  });

  it("says who can edit when this person can't", async () => {
    signIn(DANA);
    api.getRequest.mockResolvedValue(request({ can_edit: false }));
    render(EditPage);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Only the person who asked for this request can edit it.",
    );
    expect(screen.queryByLabelText("Title")).toBeNull();
  });

  it.each([
    ["0", null],
    ["41", new ApiError(404, "no")],
  ])("says a request it can't load is not found (%s)", async (id, error) => {
    nav.page.params = { id };
    api.getRequest.mockRejectedValue(error);
    render(EditPage);

    expect(await screen.findByRole("alert")).toHaveTextContent("Not found.");
  });
});
