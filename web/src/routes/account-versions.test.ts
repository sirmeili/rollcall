import { cleanup, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { browserBridge, setBridge } from "#lib/phone/bridge.ts";
import { fakeBridge } from "../test/fake-bridge.ts";
import { fakeFetch, me } from "../test/fixtures.ts";

vi.mock("$app/state", () => ({ page: { url: new URL("https://tracker.example/account") } }));
vi.mock("$app/navigation", () => ({ goto: vi.fn(), beforeNavigate: vi.fn() }));

const { session } = await import("#lib/auth/session.svelte.ts");
const AccountPage = (await import("./account/+page.svelte")).default;

/** The server answers health with `version`. */
function serverOn(version: string): void {
  vi.stubGlobal(
    "fetch",
    fakeFetch({
      "GET /health": {
        status: "ok",
        version,
        home_assistant: { mqtt: "off", events: "off" },
      },
    }),
  );
}

/** The phone app, at `version` as Android gives it (`1.4.0`, `dev`). */
function inTheApp(version: string): void {
  setBridge({ ...fakeBridge(), appVersion: `app-${version}` });
}

const NOTE = /older release/;

beforeEach(() => {
  session.user = me("viewer");
  session.loaded = true;
});

afterEach(() => {
  cleanup();
  setBridge(browserBridge);
  session.user = null;
  vi.unstubAllGlobals();
});

describe("account page, which release", () => {
  it("shows the server's version in a browser, and no app version", async () => {
    serverOn("1.4.0");

    render(AccountPage);

    expect(await screen.findByText("RollCall server 1.4.0")).toBeInTheDocument();
    expect(screen.queryByText(/RollCall app/)).toBeNull();
    expect(screen.queryByText(NOTE)).toBeNull();
  });

  it("shows a development server's version as it reports it", async () => {
    serverOn("dev (0123456)");

    render(AccountPage);

    expect(await screen.findByText("RollCall server dev (0123456)")).toBeInTheDocument();
  });

  it("shows no server version while signed out", async () => {
    session.user = null;
    const server = fakeFetch({});
    vi.stubGlobal("fetch", server);

    render(AccountPage);

    await Promise.resolve();
    expect(screen.queryByText(/RollCall server/)).toBeNull();
    expect(server.calls.filter((call) => call.path === "/health")).toEqual([]);
  });

  it("shows the app's and the server's versions in the phone app, with no note when they match", async () => {
    inTheApp("1.4.0");
    serverOn("1.4.0");

    render(AccountPage);

    expect(await screen.findByText("RollCall server 1.4.0")).toBeInTheDocument();
    expect(screen.getByText("RollCall app 1.4.0")).toBeInTheDocument();
    expect(screen.queryByText(NOTE)).toBeNull();
  });

  it("notes a server older than the app, and to update the server", async () => {
    inTheApp("1.4.0");
    serverOn("1.3.2");

    render(AccountPage);

    expect(await screen.findByText(NOTE)).toHaveTextContent(
      "The server is on an older release than this app. Update the server.",
    );
  });

  it("notes an app older than the server, and to update the app", async () => {
    inTheApp("1.4.0-rc.2");
    serverOn("1.4.0");

    render(AccountPage);

    expect(await screen.findByText(NOTE)).toHaveTextContent(
      "This app is on an older release than the server. Update the app.",
    );
  });

  it.each([
    ["an older candidate", "1.4.0-rc.1", "1.4.0-rc.10", "app"],
    ["a patch", "1.10.0", "1.9.9", "server"],
  ])("compares versions by number: %s", async (_, app, server, older) => {
    inTheApp(app);
    serverOn(server);

    render(AccountPage);

    const note = await screen.findByText(NOTE);
    expect(note).toHaveTextContent(older === "app" ? "Update the app." : "Update the server.");
  });

  it.each([
    ["a development app", "dev", "1.4.0"],
    ["a development server", "1.4.0", "dev (0123456)"],
    ["both in development", "dev", "dev"],
  ])("shows no note for %s", async (_, app, server) => {
    inTheApp(app);
    serverOn(server);

    render(AccountPage);

    expect(await screen.findByText(`RollCall server ${server}`)).toBeInTheDocument();
    expect(screen.getByText(`RollCall app ${app}`)).toBeInTheDocument();
    expect(screen.queryByText(NOTE)).toBeNull();
  });

  it("still shows the app's version when the server cannot be reached", async () => {
    inTheApp("1.4.0");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("down")));

    render(AccountPage);

    expect(screen.getByText("RollCall app 1.4.0")).toBeInTheDocument();
    await Promise.resolve();
    expect(screen.queryByText(/RollCall server/)).toBeNull();
    expect(screen.queryByText(NOTE)).toBeNull();
  });
});
