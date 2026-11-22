import { describe, expect, it } from "vitest";
import type { Me } from "#lib/api/types.ts";
import { ACCOUNT_PATH, mayOpen, navItemFor, requiredRole, visibleNav } from "#lib/nav.ts";
import type { Role } from "#lib/roles.ts";
import { me } from "../test/fixtures.ts";

function person(role: Role, requester = false, hasRequests = false): Me {
  return me(role, { username: "sam", requester, has_requests: hasRequests });
}

const labels = (role: Role | null) => visibleNav(role ? person(role) : null).map((i) => i.label);

describe("visibleNav", () => {
  it("hides admin pages from viewers and editors", () => {
    expect(labels("viewer")).toEqual([
      "Inventory",
      "Spools",
      "Products",
      "Catalog",
      "Review",
      "Shopping list",
      "Activity",
    ]);
    expect(labels("editor")).toEqual([
      "Inventory",
      "Spools",
      "Products",
      "Catalog",
      "Requests",
      "Review",
      "Shopping list",
      "Activity",
    ]);
  });

  it("shows everything to admins", () => {
    expect(labels("admin")).toContain("Users");
    expect(labels("admin")).toContain("Devices");
    expect(labels("admin")).toContain("Settings");
  });

  it("shows the Shopping list to every role, beside Review", () => {
    for (const role of ["viewer", "editor", "admin"] as const) {
      const shown = labels(role);
      expect(shown[shown.indexOf("Review") + 1]).toBe("Shopping list");
    }
  });

  it("shows nothing when signed out", () => {
    expect(labels(null)).toEqual([]);
  });

  it("shows Requests to Editors and Admins, after Catalog", () => {
    for (const role of ["editor", "admin"] as const) {
      expect(labels(role).slice(3, 5)).toEqual(["Catalog", "Requests"]);
    }
  });

  it("shows Requests to a Viewer who is or was a Requester, and to no other Viewer", () => {
    const shown = (user: Me) => visibleNav(user).some((item) => item.href === "/requests");
    expect(shown(person("viewer", true))).toBe(true);
    expect(shown(person("viewer", false, true))).toBe(true);
    expect(shown(person("viewer"))).toBe(false);
  });

  it("counts Requests as submitted and Review as waiting", () => {
    const words = Object.fromEntries(
      visibleNav(person("admin")).map((item) => [item.href, item.badgeWord]),
    );
    expect(words["/requests"]).toBe("submitted");
    expect(words["/review"]).toBe("waiting");
  });
});

describe("mayOpen", () => {
  it("follows the same rule as the nav for the Requests pages", () => {
    expect(mayOpen(person("viewer", true), "/requests/new")).toBe(true);
    expect(mayOpen(person("viewer", false, true), "/requests/4")).toBe(true);
    expect(mayOpen(person("viewer"), "/requests")).toBe(false);
    expect(mayOpen(person("editor"), "/requests/4")).toBe(true);
  });

  it("is the page's role elsewhere", () => {
    expect(mayOpen(person("editor"), "/users")).toBe(false);
    expect(mayOpen(person("admin"), "/users")).toBe(true);
    expect(mayOpen(person("viewer"), "/spools/3")).toBe(true);
    expect(mayOpen(null, "/spools/3")).toBe(false);
  });
});

describe("navItemFor", () => {
  it("matches a page and its sub-pages", () => {
    expect(navItemFor("/")?.label).toBe("Inventory");
    expect(navItemFor("/spools")?.label).toBe("Spools");
    expect(navItemFor("/spools/12")?.label).toBe("Spools");
    expect(navItemFor("/users")?.label).toBe("Users");
  });

  it("does not match lookalike paths", () => {
    expect(navItemFor("/spoolsx")).toBeUndefined();
    expect(navItemFor("/nowhere")).toBeUndefined();
  });
});

describe("requiredRole", () => {
  it("is the page's role, or viewer for pages not in the nav", () => {
    expect(requiredRole("/users")).toBe("admin");
    expect(requiredRole("/settings")).toBe("admin");
    expect(requiredRole("/devices/scanner-1")).toBe("admin");
    expect(requiredRole("/spools/3")).toBe("viewer");
    expect(requiredRole("/nowhere")).toBe("viewer");
    expect(requiredRole(ACCOUNT_PATH)).toBe("viewer");
  });
});
