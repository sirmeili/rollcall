import { afterEach, describe, expect, it, vi } from "vitest";
import * as admin from "#lib/api/admin.ts";
import { fakeFetch } from "../../test/fixtures.ts";

afterEach(() => vi.unstubAllGlobals());

describe("admin API calls", () => {
  it("send the right method, path and body", async () => {
    const page = { items: [], total: 0, limit: 50, offset: 0 };
    const fetch = fakeFetch({
      "GET /review": { flagged_events: [], unidentified_tags: [], likely_empty: [] },
      "POST /review/events/e1/accept": {},
      "POST /review/events/e1/unaccept": {},
      "POST /review/tags/A%2FB/dismiss": null,
      "POST /review/tags/A%2FB/restore": null,
      "GET /events?limit=50&offset=0": page,
      "GET /events?limit=50&offset=50&source=ui": page,
      "GET /products": [],
      "POST /products": { id: 9 },
      "POST /spools": { id: 21 },
      "GET /devices": [],
      "POST /devices": { id: "shelf", token: "t" },
      "POST /devices/shelf/rotate": { id: "shelf", token: "t2" },
      "POST /devices/shelf/revoke": null,
      "GET /users": [],
      "POST /users": { id: 4 },
      "PATCH /users/4": { id: 4 },
      "POST /auth/password": null,
      "POST /review/spools/16/dismiss": null,
      "POST /review/spools/16/restore": null,
      "GET /printers": [],
      "POST /printers/1/unpin": { id: 1 },
      "PATCH /auth/me": { id: 1, email: "frank@example.com" },
    });
    vi.stubGlobal("fetch", fetch);

    await admin.getReview();
    await admin.acceptEvent("e1");
    await admin.unacceptEvent("e1");
    await admin.dismissTag("A/B");
    await admin.restoreTag("A/B");
    expect((await admin.listEvents({ limit: 50, offset: 0 })).total).toBe(0);
    await admin.listEvents({ source: "ui", limit: 50, offset: 50 });
    await admin.listProducts();
    expect(
      (
        await admin.createProduct({
          display_name: "T",
          filament_type: "TPU",
          color_rgba: "000000FF",
        })
      ).id,
    ).toBe(9);
    await admin.addSpool({ product_id: 9, location: null, notes: "n" });
    await admin.listDevices();
    expect((await admin.registerDevice("shelf", "Shelf")).token).toBe("t");
    expect((await admin.rotateToken("shelf")).token).toBe("t2");
    await admin.revokeDevice("shelf");
    await admin.listUsers();
    await admin.createUser("sam", "viewer", "a long password");
    await admin.updateUser(4, { role: "editor" });
    await admin.changePassword("old", "new password!");
    await admin.dismissLikelyEmpty(16);
    await admin.restoreLikelyEmpty(16);
    expect(await admin.listPrinters()).toEqual([]);
    expect((await admin.unpinPrinter(1)).id).toBe(1);
    expect((await admin.updateAccount({ email: "frank@example.com" })).email).toBe(
      "frank@example.com",
    );

    expect(fetch.calls.filter((c) => c.method !== "GET")).toEqual([
      { method: "POST", path: "/review/events/e1/accept", body: undefined },
      { method: "POST", path: "/review/events/e1/unaccept", body: undefined },
      { method: "POST", path: "/review/tags/A%2FB/dismiss", body: undefined },
      { method: "POST", path: "/review/tags/A%2FB/restore", body: undefined },
      {
        method: "POST",
        path: "/products",
        body: { display_name: "T", filament_type: "TPU", color_rgba: "000000FF" },
      },
      { method: "POST", path: "/spools", body: { product_id: 9, location: null, notes: "n" } },
      { method: "POST", path: "/devices", body: { id: "shelf", name: "Shelf" } },
      { method: "POST", path: "/devices/shelf/rotate", body: undefined },
      { method: "POST", path: "/devices/shelf/revoke", body: undefined },
      {
        method: "POST",
        path: "/users",
        body: { username: "sam", role: "viewer", password: "a long password", requester: false },
      },
      { method: "PATCH", path: "/users/4", body: { role: "editor" } },
      {
        method: "POST",
        path: "/auth/password",
        body: { current_password: "old", new_password: "new password!" },
      },
      { method: "POST", path: "/review/spools/16/dismiss", body: undefined },
      { method: "POST", path: "/review/spools/16/restore", body: undefined },
      { method: "POST", path: "/printers/1/unpin", body: undefined },
      { method: "PATCH", path: "/auth/me", body: { email: "frank@example.com" } },
    ]);
  });

  it("resolve a possible duplicate and bring it back", async () => {
    const fetch = fakeFetch({
      "POST /review/duplicates/3/same-product": null,
      "POST /review/duplicates/3/keep-separate": null,
      "POST /review/duplicates/3/restore": null,
    });
    vi.stubGlobal("fetch", fetch);

    await admin.sameProduct(3, 7);
    await admin.keepSeparate(3);
    await admin.restoreDuplicate(3);

    expect(fetch.calls).toEqual([
      { method: "POST", path: "/review/duplicates/3/same-product", body: { candidate_id: 7 } },
      { method: "POST", path: "/review/duplicates/3/keep-separate", body: undefined },
      { method: "POST", path: "/review/duplicates/3/restore", body: undefined },
    ]);
  });
});
