import { describe, expect, it } from "vitest";
import type { Catalog, CatalogColor } from "#lib/api/catalog.ts";
import type { Choice, HistoryEntry, PrintRequest } from "#lib/api/requests.ts";
import {
  blankForm,
  editBody,
  fileProblem,
  formFrom,
  formProblems,
  isWebLink,
  requestBody,
  summaryHeading,
  type RequestForm,
} from "#lib/requests/form.ts";
import {
  historyDetail,
  historyTitle,
  listText,
  neededByDate,
  relativeDay,
  similarText,
  sizeText,
} from "#lib/requests/labels.ts";
import { whyNoEdit } from "#lib/requests/access.ts";
import { chosenFrom, chosenSub, pickerOptions, searchOptions } from "#lib/requests/picker.ts";
import { me, product, summary } from "../../test/fixtures.ts";

const TODAY = "2026-11-18";

function entry(fields: Partial<HistoryEntry>): HistoryEntry {
  return {
    kind: "submitted",
    username: "sam",
    at: "2026-11-18T10:00:00Z",
    fields: null,
    from_value: null,
    to_value: null,
    note: null,
    ...fields,
  };
}

function color(name: string, fields: Partial<CatalogColor> = {}): CatalogColor {
  return {
    uuid: name.toLowerCase(),
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

function catalog(colors: CatalogColor[]): Catalog {
  return {
    lines: [{ uuid: "pla-basic", name: "PLA Basic", material: "PLA", colors }],
    synced: true,
    dataset_version: "1",
    last_success_at: null,
    cutoff: 10,
    out_of_date: false,
    store_address: "https://store.example",
  };
}

function choice(fields: Partial<Choice>): Choice {
  return {
    kind: "catalog_color",
    note: "",
    name: "Hot Pink PLA Basic",
    hexes: ["FF69B4"],
    material: "PLA",
    product_id: null,
    sealed: null,
    open: null,
    catalog_color: "hot-pink",
    color_name: "Hot Pink",
    line: "PLA Basic",
    bambu_code: null,
    in_catalog: true,
    multi_color: false,
    similar: [],
    ...fields,
  };
}

function filled(fields: Partial<RequestForm> = {}): RequestForm {
  return {
    ...blankForm(),
    title: "Wingspan insert",
    link: "https://makerworld.com/models/1",
    choices: [chosenFrom(choice({}))],
    ...fields,
  };
}

describe("request words", () => {
  it.each([
    ["2026-11-18", "today"],
    ["2026-11-19", "tomorrow"],
    ["2026-11-21", "in 3 days"],
    ["2026-11-17", "yesterday"],
    ["2026-11-08", "10 days ago"],
    ["2026-12-01", "in 13 days"],
  ])("says %s relative to today as %s", (day, text) => {
    expect(relativeDay(day, TODAY)).toBe(text);
  });

  it("shows a needed-by day without moving it by time zone", () => {
    expect(neededByDate("2026-11-24")).toBe("Nov 24");
  });

  it("joins words as a sentence does", () => {
    expect(listText([])).toBe("");
    expect(listText(["notes"])).toBe("notes");
    expect(listText(["notes", "needed by"])).toBe("notes and needed by");
    expect(listText(["a", "b", "c"])).toBe("a, b and c");
  });

  it("describes each kind of history entry", () => {
    expect(historyTitle(entry({}))).toBe("Submitted by sam");
    const edited = entry({ kind: "edited", fields: ["notes", "needed_by"] });
    expect(historyTitle(edited)).toBe("Edited by sam");
    expect(historyDetail(edited)).toBe("Changed notes and needed by");
    const changed = entry({
      kind: "priority_changed",
      username: null,
      from_value: "normal",
      to_value: "urgent",
    });
    expect(historyTitle(changed)).toBe("Priority changed");
    expect(historyDetail(changed)).toBe("Normal → Urgent");
    expect(historyDetail(entry({}))).toBeNull();
  });

  it("gives file sizes in KB or MB", () => {
    expect(sizeText(19_503_513)).toBe("18.6 MB");
    expect(sizeText(740 * 1024)).toBe("740 KB");
    expect(sizeText(10)).toBe("1 KB");
  });

  it("says what is similar in stock", () => {
    expect(similarText(null)).toBe("Multi-color: no comparison");
    expect(similarText([])).toBe("No similar color in stock");
    expect(similarText(["A", "B", "C", "D"], 2)).toBe("Similar in stock: A, B +2");
    expect(similarText(["A"])).toBe("Similar in stock: A");
  });
});

describe("the filament picker", () => {
  const inventory = [
    summary({
      product: product({ id: 7, display_name: "Blue PLA", color_rgba: "0a2ca5ff" }),
      counts: { sealed: 2, open: 1, empty: 0, unknown: 0 },
    }),
    summary({
      product: product({ id: 8, display_name: "Used up PLA" }),
      counts: { sealed: 0, open: 0, empty: 4, unknown: 0 },
    }),
  ];
  const options = pickerOptions(
    inventory,
    catalog([
      color("Hot Pink", { bambu_code: "10203" }),
      color("Owned White", { owned: true }),
      color("Old Gold", { discontinued: true }),
      color("Rainbow", { multi_color: true, hexes: ["FF0000", "00FF00"] }),
    ]),
  );

  it("offers in-stock products, then catalog colors no one has in stock", () => {
    expect(options.products.map((o) => [o.key, o.name, o.hexes, o.sub])).toEqual([
      ["p:7", "Blue PLA", ["0A2CA5"], "PLA · 2 sealed · 1 open"],
    ]);
    expect(options.colors.map((o) => [o.key, o.name, o.sub])).toEqual([
      ["c:hot pink", "Hot Pink PLA Basic", "PLA · 10203 · not in stock"],
      ["c:rainbow", "Rainbow PLA Basic", "PLA · not in stock"],
    ]);
    expect(chosenSub(options.colors[1])).toBe("PLA · not in stock · Multi-color: no comparison");
  });

  it("works before the catalog is downloaded", () => {
    expect(pickerOptions([], null)).toEqual({ products: [], colors: [] });
  });

  it("shows the first products until something is typed", () => {
    const result = searchOptions(options, " ");
    expect(result.products).toHaveLength(1);
    expect(result.colors).toEqual([]);
    expect(result.summary).toBe(
      "Showing 1 of your 1 products. Type to search all of them and the catalog.",
    );
  });

  it("searches products and catalog colors by every word", () => {
    const result = searchOptions(options, "pink pla");
    expect(result.colors.map((o) => o.name)).toEqual(["Hot Pink PLA Basic"]);
    expect(result.summary).toBe("0 of your products, 1 catalog color");
    expect(searchOptions(options, "10203").colors).toHaveLength(1);
    expect(searchOptions(options, "zzz").summary).toBe('Nothing matches "zzz".');
  });

  it("shows at most five catalog colors", () => {
    const many = pickerOptions([], catalog(["A", "B", "C", "D", "E", "F"].map((n) => color(n))));
    const result = searchOptions(many, "pla");
    expect(result.colors).toHaveLength(5);
    expect(result.summary).toBe("0 of your products, 6 catalog colors (showing 5)");
  });

  it("shows a saved choice with what is known now", () => {
    const gone = chosenFrom(choice({ in_catalog: false, material: null }));
    expect(chosenSub(gone)).toBe("No longer in the catalog");
    const owned = chosenFrom(
      choice({ kind: "product", product_id: 7, name: "Blue PLA", sealed: 0, open: 0 }),
    );
    expect([owned.key, owned.sub]).toEqual(["p:7", "PLA · none left"]);
  });
});

describe("the request form", () => {
  it("needs a title, a quantity of 1 to 100, a filament and a model", () => {
    const problems = formProblems({ ...blankForm(), quantity: "0" }, TODAY);
    expect(problems.map((p) => p.field)).toEqual(["title", "quantity", "notes", "choices"]);
    expect(formProblems(filled({ quantity: "2.5" }), TODAY)[0].field).toBe("quantity");
    expect(formProblems(filled(), TODAY)).toEqual([]);
  });

  it("takes notes that say where the model is instead of a file or link", () => {
    expect(formProblems(filled({ link: "", notes: "On the USB stick" }), TODAY)).toEqual([]);
  });

  it("refuses a past needed-by date, on an edit too", () => {
    expect(formProblems(filled({ neededBy: "2026-11-10" }), TODAY)[0].message).toBe(
      "Needed by can't be in the past. Pick today or later, or leave it empty.",
    );
    expect(formProblems(filled({ neededBy: TODAY }), TODAY)).toEqual([]);
  });

  it("doesn't count a file missing from disk as the model", () => {
    const missing = filled({
      link: "",
      file: { status: "kept", name: "lamp.3mf", size: 5, missing: true },
    });
    expect(formProblems(missing, TODAY).map((p) => p.field)).toEqual(["notes"]);
    expect(formProblems({ ...missing, notes: "On the USB stick" }, TODAY)).toEqual([]);
  });

  it.each([
    ["makerworld.com/models/1", false],
    ["ftp://example.com/a", false],
    ["https://", false],
    ["http://example.com/a", true],
  ])("checks %s is a web link", (link, ok) => {
    expect(isWebLink(link)).toBe(ok);
  });

  it("waits for an upload to finish or be removed", () => {
    const uploading = filled({
      file: { status: "uploading", name: "dragon.3mf", size: 10, percent: 38 },
    });
    expect(formProblems(uploading, TODAY)[0].message).toBe(
      "dragon.3mf is still uploading. Wait for it to finish, or cancel it.",
    );
    const failed = filled({
      file: { status: "failed", name: "dragon.3mf", size: 10, percent: 61, message: "x" },
    });
    expect(formProblems(failed, TODAY)[0].message).toBe(
      "dragon.3mf didn't upload. Try again, or remove it.",
    );
  });

  it("takes only 3MF and STL files up to 95 MB", () => {
    expect(fileProblem("stand.obj", 10)).toBe(
      "stand.obj isn't a 3MF or STL file. Choose a .3mf or .stl file.",
    );
    expect(fileProblem("plate.3MF", 138_832_691)).toBe(
      "plate.3MF is 132.4 MB. Files can be up to 95 MB.",
    );
    expect(fileProblem("part.stl", 95 * 1024 * 1024)).toBeNull();
  });

  it("sends trimmed fields and the choices in order", () => {
    const form = filled({
      title: " Insert ",
      quantity: "3",
      neededBy: "2026-12-05",
      notes: " 0.2 mm ",
      file: { status: "uploaded", upload: { id: "u1", name: "a.3mf", size: 1, kind: "3mf" } },
      choices: [
        { ...chosenFrom(choice({ kind: "product", product_id: 7 })), note: " body " },
        chosenFrom(choice({})),
      ],
    });
    expect(requestBody(form)).toEqual({
      title: "Insert",
      notes: "0.2 mm",
      quantity: 3,
      needed_by: "2026-12-05",
      priority: "normal",
      link: "https://makerworld.com/models/1",
      choices: [
        { product_id: 7, note: "body" },
        { catalog_color: "hot-pink", note: "" },
      ],
      upload_id: "u1",
    });
  });

  it("edits a request, keeping or removing its file", () => {
    const request = {
      title: "Lamp",
      notes: "",
      quantity: 1,
      needed_by: null,
      priority: "urgent",
      link: null,
      file: { name: "lamp.3mf", size: 5, kind: "3mf", missing: false },
      choices: [choice({})],
    } as unknown as PrintRequest;
    const form = formFrom(request);
    expect(form.file).toEqual({ status: "kept", name: "lamp.3mf", size: 5, missing: false });
    expect(editBody(form)).toMatchObject({ upload_id: null, remove_file: false, link: null });
    expect(editBody({ ...form, file: { status: "none" } }).remove_file).toBe(true);
    expect(formFrom({ ...request, file: null }).file).toEqual({ status: "none" });
  });

  it("counts the things to fix", () => {
    expect(summaryHeading(1, false)).toBe("Fix 1 thing before submitting");
    expect(summaryHeading(3, true)).toBe("Fix 3 things before saving");
  });
});

describe("why a request can't be edited", () => {
  const sams = { can_edit: false, requester: { id: 2, username: "sam" } } as PrintRequest;
  const sam = me("viewer", { id: 2, username: "sam", requester: true });

  it("names the reason for each person", () => {
    expect(whyNoEdit(sam, { ...sams, can_edit: true })).toBeNull();
    expect(whyNoEdit(me("editor", { id: 3 }), sams)).toBe(
      "Only the person who asked for this request can edit it.",
    );
    expect(whyNoEdit(null, sams)).toBe("Only the person who asked for this request can edit it.");
    expect(whyNoEdit({ ...sam, requester: false }, sams)).toBe(
      "You can no longer edit this request: you're no longer a Requester.",
    );
    expect(whyNoEdit(sam, sams)).toBe("This request can no longer be edited.");
  });
});
