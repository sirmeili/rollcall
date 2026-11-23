import { render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { GroupOut, SettingOut } from "#lib/api/settings.ts";
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

const FIREBASE: GroupOut = {
  group: "phone-notifications",
  settings: [
    setting("firebase_project_id", { value: "rollcall-12345", set: true, source: "app" }),
    setting("firebase_app_id"),
    setting("firebase_api_key"),
    setting("firebase_sender_id"),
    setting("firebase_service_account", { secret: true, set: true, source: "env", has_env: true }),
  ],
};

const NEVER_SYNCED = {
  last_success_at: null,
  last_attempt_at: null,
  last_result: null,
  last_reason: null,
  dataset_version: null,
};

function serve(routes: Parameters<typeof fakeFetch>[0]) {
  const fetch = fakeFetch({
    "GET /settings/general": { group: "general", settings: [] },
    "GET /settings/scanners": { group: "scanners", settings: [] },
    "GET /settings/home-assistant": { group: "home-assistant", settings: [] },
    "GET /settings/catalog": { group: "catalog", settings: [] },
    "GET /catalog/sync": { colors: 0, ofdb: NEVER_SYNCED, bambustudio: NEVER_SYNCED },
    "GET /tokens": [],
    "GET /settings/email": { group: "email", settings: [] },
    "GET /settings/email/status": { on: false, last_success: null, last_failure: null },
    "GET /settings/phone-notifications": FIREBASE,
    ...routes,
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

function form() {
  return within(screen.getByRole("form", { name: "Phone notifications" }));
}

afterEach(() => vi.unstubAllGlobals());

describe("Settings page, Phone notifications", () => {
  it("shows the Firebase settings, never the service-account key", async () => {
    serve({});
    render(SettingsPage);

    expect(await screen.findByLabelText("Firebase project ID")).toHaveValue("rollcall-12345");
    expect(screen.getByLabelText("App ID")).toHaveValue("");
    expect(screen.getByLabelText("API key")).toHaveValue("");
    expect(screen.getByLabelText("Sender ID")).toHaveValue("");
    const key = screen.getByLabelText("Service-account key");
    expect(key).toHaveValue("");
    expect(key).toHaveAttribute("type", "password");
    expect(key).toHaveAttribute("placeholder", "Saved. Leave empty to keep it.");
    expect(form().getByText("From .env")).toBeInTheDocument();
  });

  it("saves the key pasted in, and says what takes effect when", async () => {
    const fetch = serve({
      "PUT /settings/phone-notifications": FIREBASE,
    });
    render(SettingsPage);

    await userEvent.type(await screen.findByLabelText("Sender ID"), "123456789012");
    await userEvent.click(screen.getByLabelText("Service-account key"));
    await userEvent.paste('{"type": "service_account"}');
    await userEvent.click(form().getByRole("button", { name: "Save" }));

    expect(fetch.calls.at(-1)).toEqual({
      method: "PUT",
      path: "/settings/phone-notifications",
      body: {
        values: {
          firebase_sender_id: "123456789012",
          firebase_service_account: '{"type": "service_account"}',
        },
        clear: [],
      },
    });
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Saved. Phones get the new settings the next time they open, and restart to use them.",
    );
  });
});
