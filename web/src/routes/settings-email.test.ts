import { render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { EmailStatus, GroupOut, SettingOut } from "#lib/api/settings.ts";
import { setTimeZone } from "#lib/format.ts";
import { fakeFetch } from "../test/fixtures.ts";

const SettingsPage = (await import("./settings/+page.svelte")).default;

function setting(key: string, fields: Partial<SettingOut> = {}): SettingOut {
  return {
    key,
    value: null,
    secret: false,
    set: false,
    source: "default",
    has_env: false,
    unreadable: false,
    ...fields,
  };
}

const EMAIL: GroupOut = {
  group: "email",
  settings: [
    setting("smtp_host", { value: "smtp.example.com", set: true, source: "app" }),
    setting("smtp_port", { value: "587", set: true }),
    setting("smtp_security", { value: "starttls", set: true }),
    setting("smtp_user", { value: "rollcall@example.com", set: true, source: "app" }),
    setting("smtp_password", { secret: true, set: true, source: "app" }),
    setting("smtp_from", { value: "RollCall <rollcall@example.com>", set: true, source: "app" }),
    setting("public_url"),
  ],
};

const NEVER_SYNCED = {
  last_success_at: null,
  last_attempt_at: null,
  last_result: null,
  last_reason: null,
  dataset_version: null,
};

const NOTHING_SENT: EmailStatus = { on: true, last_success: null, last_failure: null };

function serve(routes: Parameters<typeof fakeFetch>[0]) {
  const fetch = fakeFetch({
    "GET /settings/general": { group: "general", settings: [] },
    "GET /settings/scanners": { group: "scanners", settings: [] },
    "GET /settings/home-assistant": { group: "home-assistant", settings: [] },
    "GET /settings/catalog": { group: "catalog", settings: [] },
    "GET /catalog/sync": { colors: 0, ofdb: NEVER_SYNCED, bambustudio: NEVER_SYNCED },
    "GET /tokens": [],
    "GET /settings/phone-notifications": { group: "phone-notifications", settings: [] },
    "GET /settings/email": EMAIL,
    "GET /settings/email/status": NOTHING_SENT,
    ...routes,
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

function form() {
  return within(screen.getByRole("form", { name: "Email" }));
}

function card() {
  return within(screen.getByRole("region", { name: "Email" }));
}

beforeEach(() => setTimeZone("UTC"));
afterEach(() => vi.unstubAllGlobals());

describe("Settings page, Email", () => {
  it("shows the seven settings, never the password", async () => {
    serve({});
    render(SettingsPage);

    expect(await screen.findByLabelText("SMTP host")).toHaveValue("smtp.example.com");
    expect(screen.getByLabelText("Port")).toHaveValue("587");
    expect(screen.getByLabelText("Security")).toHaveValue("starttls");
    expect(screen.getByLabelText("User")).toHaveValue("rollcall@example.com");
    const password = screen.getByLabelText("Password");
    expect(password).toHaveValue("");
    expect(password).toHaveAttribute("type", "password");
    expect(screen.getByLabelText("From address")).toHaveValue("RollCall <rollcall@example.com>");
    expect(screen.getByLabelText("Public URL")).toHaveValue("");
  });

  it("saves only what changed", async () => {
    const fetch = serve({ "PUT /settings/email": EMAIL });
    render(SettingsPage);

    await userEvent.type(
      await screen.findByLabelText("Public URL"),
      "https://rollcall.example.com",
    );
    await userEvent.click(form().getByRole("button", { name: "Save" }));

    expect(fetch.calls.at(-1)).toEqual({
      method: "PUT",
      path: "/settings/email",
      body: { values: { public_url: "https://rollcall.example.com" }, clear: [] },
    });
  });

  it("sends a test email and shows the result", async () => {
    const fetch = serve({
      "POST /settings/email/test": { ok: true, message: "Sent a test email to frank@example.com." },
    });
    render(SettingsPage);

    await screen.findByLabelText("SMTP host");
    await userEvent.click(form().getByRole("button", { name: "Send test email" }));

    const results = await form().findByRole("list", { name: "Test results" });
    expect(results).toHaveTextContent("Sent a test email to frank@example.com.");
    expect(fetch.calls.at(-2)).toEqual({
      method: "POST",
      path: "/settings/email/test",
      body: undefined,
    });
    // The last success and failure are read again after the test.
    expect(fetch.calls.at(-1)).toMatchObject({ method: "GET", path: "/settings/email/status" });
  });

  it("shows a failed test email", async () => {
    serve({
      "POST /settings/email/test": {
        ok: false,
        message: "The mail server refused the user name or password.",
      },
    });
    render(SettingsPage);

    await screen.findByLabelText("SMTP host");
    await userEvent.click(form().getByRole("button", { name: "Send test email" }));

    const results = await form().findByRole("list", { name: "Test results" });
    expect(within(results).getByRole("listitem")).toHaveTextContent(
      "The mail server refused the user name or password.",
    );
    expect(within(results).getByRole("listitem")).not.toHaveClass("ok");
  });

  it("shows the server's wait message when a test email comes too soon", async () => {
    serve({
      "POST /settings/email/test": new Response(
        JSON.stringify({ detail: "Wait a few seconds before sending another test email." }),
        { status: 429 },
      ),
    });
    render(SettingsPage);

    await screen.findByLabelText("SMTP host");
    await userEvent.click(form().getByRole("button", { name: "Send test email" }));

    const results = await form().findByRole("list", { name: "Test results" });
    expect(within(results).getByRole("listitem")).toHaveTextContent(
      "Wait a few seconds before sending another test email.",
    );
    expect(within(results).getByRole("listitem")).not.toHaveClass("ok");
  });

  it("shows any other error from Send test email as the card's message", async () => {
    serve({
      "POST /settings/email/test": new Response(JSON.stringify({ detail: "Forbidden" }), {
        status: 403,
      }),
    });
    render(SettingsPage);

    await screen.findByLabelText("SMTP host");
    await userEvent.click(form().getByRole("button", { name: "Send test email" }));

    expect(await form().findByRole("status")).toHaveTextContent("Your role cannot do that.");
    expect(form().queryByRole("list", { name: "Test results" })).toBeNull();
  });

  it("shows the last success and the last failure", async () => {
    serve({
      "GET /settings/email/status": {
        on: true,
        last_success: "2026-11-18T14:05:00Z",
        last_failure: {
          at: "2026-11-19T09:30:00Z",
          message: "Can't reach the mail server. Check the host and port.",
        },
      },
    });
    render(SettingsPage);

    const success = await card().findByText(/Last sent/);
    expect(success).toHaveTextContent("Nov 18");
    const failure = card().getByText(/Last failure/);
    expect(failure).toHaveTextContent("Nov 19");
    expect(failure).toHaveTextContent("Can't reach the mail server. Check the host and port.");
  });

  it("says when nothing has been sent, and when email is off", async () => {
    serve({});
    const { unmount } = render(SettingsPage);
    expect(await card().findByText("Nothing sent since the server started.")).toBeInTheDocument();
    unmount();

    serve({ "GET /settings/email/status": { ...NOTHING_SENT, on: false } });
    render(SettingsPage);
    expect(await card().findByText("Email is off until an SMTP host is set.")).toBeInTheDocument();
  });
});
