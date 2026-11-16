import { render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Catalog, CatalogColor, FilamentLine } from "#lib/api/catalog.ts";
import { session } from "#lib/auth/session.svelte.ts";
import { setTimeZone } from "#lib/format.ts";
import type { Role } from "#lib/roles.ts";
import { viewport } from "#lib/viewport.svelte.ts";
import { fakeFetch } from "../test/fixtures.ts";

const CatalogPage = (await import("./catalog/+page.svelte")).default;

function color(name: string, hexes: string[], fields: Partial<CatalogColor> = {}): CatalogColor {
  return {
    uuid: `${name}-${hexes.join("")}`,
    name,
    hexes,
    discontinued: false,
    multi_color: hexes.length > 1,
    ...fields,
  };
}

function line(name: string, material: string, colors: CatalogColor[]): FilamentLine {
  return { uuid: name.toLowerCase().replace(/ /g, "-"), name, material, colors };
}

const LINES: FilamentLine[] = [
  line("PLA Basic", "PLA", [
    color("Jade White", ["FFFFFF"]),
    color("Blue", ["0A2CA5"]),
    color("Bronze", ["847D48"], { discontinued: true }),
  ]),
  line("PLA Silk Dual Color", "PLA", [color("Gold-Silver", ["F4A925", "C0C0C0"])]),
  line("PETG HF", "PETG", [color("Blue", ["002E96"]), color("Black", ["000000"])]),
  line("ABS", "ABS", [color("Azure", ["489FDF"])]),
];

const SYNCED: Catalog = {
  lines: LINES,
  synced: true,
  dataset_version: "2026.11.15",
  last_success_at: "2026-11-15T04:00:00Z",
};

const NEVER: Catalog = { lines: [], synced: false, dataset_version: null, last_success_at: null };

function serve(routes: Parameters<typeof fakeFetch>[0]) {
  const fetch = fakeFetch(routes);
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

function signIn(role: Role): void {
  session.user = { id: 1, username: "frank", role, time_zone: "UTC" };
}

async function open(catalog: Catalog = SYNCED, role: Role = "viewer") {
  signIn(role);
  const fetch = serve({ "GET /catalog": catalog });
  render(CatalogPage);
  return fetch;
}

function group(name: string) {
  return within(screen.getByRole("region", { name: new RegExp(`^${name} ·`) }));
}

function headings(): string[] {
  return screen
    .queryAllByRole("button", { expanded: true })
    .concat(screen.queryAllByRole("button", { expanded: false }))
    .map((button) => button.textContent?.replace(/\s+/g, " ").trim() ?? "")
    .sort();
}

function summary(): string {
  return screen.getByText(/catalog colors in/).textContent ?? "";
}

beforeEach(() => {
  vi.useFakeTimers({ now: new Date("2026-11-16T12:00:00Z"), shouldAdvanceTime: true });
  setTimeZone("UTC");
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  setTimeZone(undefined);
  session.user = null;
  viewport().phone = false;
});

describe("Catalog page", () => {
  it("lists each filament line as a heading with its material and color count", async () => {
    await open();

    await screen.findByText("Jade White");
    expect(headings()).toEqual([
      "ABS · ABS · 1 color",
      "PETG HF · PETG · 2 colors",
      "PLA Basic · PLA · 2 colors",
      "PLA Silk Dual Color · PLA · 1 color",
    ]);
    const order = screen.getAllByRole("region").map((r) => r.getAttribute("aria-labelledby"));
    expect(order).toEqual([
      "line-pla-basic",
      "line-pla-silk-dual-color",
      "line-petg-hf",
      "line-abs",
    ]);
    expect(summary()).toBe("6 catalog colors in 4 filament lines");
  });

  it("shows each color's name and hex, and splits a multi-color catalog color", async () => {
    await open();

    await screen.findByText("Jade White");
    expect(group("PLA Basic").getByText("#FFFFFF")).toBeInTheDocument();
    const dual = group("PLA Silk Dual Color");
    expect(dual.getByText("#F4A925 / #C0C0C0")).toBeInTheDocument();
    expect(dual.getByText("Multi-color")).toBeInTheDocument();
    expect(group("PLA Basic").queryByText("Multi-color")).toBeNull();
  });

  it("collapses and expands a filament line", async () => {
    await open();

    const heading = await screen.findByRole("button", { name: /^PLA Basic ·/ });
    await userEvent.click(heading);

    expect(heading).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Jade White")).toBeNull();
    await userEvent.click(heading);
    expect(heading).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Jade White")).toBeInTheDocument();
  });

  it("hides discontinued colors until Show discontinued is on", async () => {
    await open();

    await screen.findByText("Jade White");
    expect(screen.queryByText("Bronze")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Show discontinued" }));

    expect(group("PLA Basic").getByText("Bronze")).toBeInTheDocument();
    expect(group("PLA Basic").getByText("Discontinued")).toBeInTheDocument();
    expect(summary()).toBe("7 of 7 catalog colors in 4 filament lines");
  });

  it("searches color names", async () => {
    await open();

    await userEvent.type(await screen.findByLabelText("Search line or color"), "blue");

    expect(headings()).toEqual([
      "PETG HF · PETG · 1 of 2 colors",
      "PLA Basic · PLA · 1 of 2 colors",
    ]);
    expect(summary()).toBe("2 of 6 catalog colors in 2 filament lines");
  });

  it("shows the whole line when the search matches its name", async () => {
    await open();

    await userEvent.type(await screen.findByLabelText("Search line or color"), "petg");

    expect(headings()).toEqual(["PETG HF · PETG · 2 colors"]);
    expect(screen.getByText("Black")).toBeInTheDocument();
  });

  it("filters by several materials at once", async () => {
    await open();

    await screen.findByText("Jade White");
    await userEvent.click(screen.getByRole("button", { name: "PETG" }));
    await userEvent.click(screen.getByRole("button", { name: "ABS" }));

    expect(headings()).toEqual(["ABS · ABS · 1 color", "PETG HF · PETG · 2 colors"]);
    expect(summary()).toBe("3 of 6 catalog colors in 2 filament lines");
    await userEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(summary()).toBe("6 catalog colors in 4 filament lines");
  });

  it("says when nothing matches, with a way to clear", async () => {
    await open();

    await userEvent.type(await screen.findByLabelText("Search line or color"), "chartreuse");

    expect(screen.getByText(/No catalog colors match/)).toBeInTheDocument();
    expect(summary()).toBe("0 of 6 catalog colors in 0 filament lines");
    await userEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(screen.getByLabelText("Search line or color")).toHaveValue("");
    expect(screen.getByText("Jade White")).toBeInTheDocument();
  });

  it("names the source, its license, the last update and the dataset version", async () => {
    await open();

    expect(
      await screen.findByText(
        "Catalog data from the Open Filament Database (MIT license) · Updated Nov 15, dataset v2026.11.15",
      ),
    ).toBeInTheDocument();
  });

  it("tells a Viewer before the first sync that an admin can download it", async () => {
    await open(NEVER, "viewer");

    expect(
      await screen.findByRole("heading", { name: "The catalog hasn't been downloaded yet." }),
    ).toBeInTheDocument();
    expect(screen.getByText("An admin can download it from Settings.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Refresh now" })).toBeNull();
  });

  it("lets an Admin download it before the first sync", async () => {
    signIn("admin");
    let synced = false;
    serve({
      "GET /catalog": () => (synced ? SYNCED : NEVER),
      "POST /catalog/sync": () => {
        synced = true;
        return { last_result: "updated", dataset_version: "2026.11.15", colors: 7 };
      },
    });
    render(CatalogPage);

    expect(await screen.findByRole("link", { name: "Catalog settings" })).toHaveAttribute(
      "href",
      "/settings",
    );
    await userEvent.click(screen.getByRole("button", { name: "Refresh now" }));

    expect(await screen.findByText("Jade White")).toBeInTheDocument();
  });

  it("says why Refresh now did not download it", async () => {
    signIn("admin");
    serve({
      "GET /catalog": NEVER,
      "POST /catalog/sync": { last_result: "failed", last_reason: "could not reach OFDB" },
    });
    render(CatalogPage);

    await userEvent.click(await screen.findByRole("button", { name: "Refresh now" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Sync failed: could not reach OFDB.",
    );
  });

  it("says why the catalog could not be read, and tries again", async () => {
    signIn("viewer");
    let fail = true;
    serve({
      "GET /catalog": () =>
        fail ? new Response(JSON.stringify({ detail: "boom" }), { status: 500 }) : SYNCED,
    });
    render(CatalogPage);

    expect(await screen.findByRole("alert")).toHaveTextContent("boom.");
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Jade White")).toBeInTheDocument();
  });
});

describe("Catalog page on a phone", () => {
  beforeEach(() => {
    viewport().phone = true;
  });

  it("moves the filters into a filter sheet", async () => {
    await open();

    await screen.findByText("Jade White");
    expect(screen.queryByRole("button", { name: "PETG" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Filter" }));
    const sheet = within(screen.getByRole("dialog", { name: "Filter" }));
    await userEvent.click(sheet.getByRole("button", { name: "PETG 2" }));
    await userEvent.click(sheet.getByRole("checkbox", { name: "Show discontinued" }));
    expect(sheet.getByRole("button", { name: "PLA 4" })).toBeInTheDocument();
    await userEvent.click(sheet.getByRole("button", { name: "Show 2 colors" }));

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(headings()).toEqual(["PETG HF · PETG · 2 colors"]);
    expect(screen.getByRole("button", { name: "Filter, 2 on" })).toBeInTheDocument();
    const quick = within(screen.getByRole("group", { name: "Quick filters" }));
    expect(quick.getByRole("button", { name: "PETG" })).toBeInTheDocument();
    await userEvent.click(quick.getByRole("button", { name: "Hide discontinued colors" }));
    await userEvent.click(quick.getByRole("button", { name: "Clear the types" }));
    expect(summary()).toBe("6 catalog colors in 4 filament lines");
  });

  it("leaves the filter as it was when the sheet is closed", async () => {
    await open();

    await screen.findByText("Jade White");
    await userEvent.click(screen.getByRole("button", { name: "Filter" }));
    const sheet = within(screen.getByRole("dialog", { name: "Filter" }));
    await userEvent.click(sheet.getByRole("button", { name: "ABS 1" }));
    await userEvent.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(summary()).toBe("6 catalog colors in 4 filament lines");
  });

  it("clears the sheet's choices", async () => {
    await open();

    await screen.findByText("Jade White");
    await userEvent.click(screen.getByRole("button", { name: "Filter" }));
    const sheet = within(screen.getByRole("dialog", { name: "Filter" }));
    await userEvent.click(sheet.getByRole("button", { name: "ABS 1" }));
    await userEvent.click(sheet.getByRole("button", { name: "Clear" }));

    expect(sheet.getByRole("button", { name: "Show 6 colors" })).toBeInTheDocument();
    await userEvent.click(sheet.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
