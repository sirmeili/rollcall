import type { Me } from "#lib/api/types.ts";
import { canOpenRequests, canSubmit } from "#lib/requests/access.ts";
import { allows, type Role } from "#lib/roles.ts";

export interface NavItem {
  href: string;
  label: string;
  role: Role;
  /** What the link's count counts, read out with it ("Review, 3 waiting"). */
  badgeWord: string;
  /** Who may open it, when that is more than a role. */
  allowed?: (user: Me) => boolean;
}

/** Reached from the account button in the header rather than the nav links. Any signed-in
 * user may open it. */
export const ACCOUNT_PATH = "/account";

/** The request form. */
export const NEW_REQUEST_PATH = "/requests/new";

const WAITING = "waiting";

/** The pages of the web app, with the lowest role that may open each. The API enforces the
 * same rules. */
export const NAV: readonly NavItem[] = [
  { href: "/", label: "Inventory", role: "viewer", badgeWord: WAITING },
  { href: "/spools", label: "Spools", role: "viewer", badgeWord: WAITING },
  { href: "/products", label: "Products", role: "viewer", badgeWord: WAITING },
  { href: "/catalog", label: "Catalog", role: "viewer", badgeWord: WAITING },
  // Editors and Admins, Requesters, and anyone who has made a request (ADR-0017).
  {
    href: "/requests",
    label: "Requests",
    role: "viewer",
    badgeWord: "submitted",
    allowed: canOpenRequests,
  },
  { href: "/review", label: "Review", role: "viewer", badgeWord: WAITING },
  { href: "/activity", label: "Activity", role: "viewer", badgeWord: WAITING },
  { href: "/devices", label: "Devices", role: "admin", badgeWord: WAITING },
  { href: "/users", label: "Users", role: "admin", badgeWord: WAITING },
  { href: "/settings", label: "Settings", role: "admin", badgeWord: WAITING },
];

function itemAllows(item: NavItem, user: Me | null | undefined): boolean {
  if (!user || !allows(user.role, item.role)) return false;
  return item.allowed ? item.allowed(user) : true;
}

export function visibleNav(user: Me | null | undefined): NavItem[] {
  return NAV.filter((item) => itemAllows(item, user));
}

function matches(item: NavItem, pathname: string): boolean {
  if (item.href === "/") return pathname === "/";
  return pathname === item.href || pathname.startsWith(item.href + "/");
}

/** The nav item a path belongs to: the page itself or one of its sub-pages. */
export function navItemFor(pathname: string): NavItem | undefined {
  return NAV.find((item) => matches(item, pathname));
}

/** The lowest role that may open a path; pages not in the nav need a Viewer. */
export function requiredRole(pathname: string): Role {
  return navItemFor(pathname)?.role ?? "viewer";
}

/** Whether the user may open a path: its nav item's rule, or a Viewer's role elsewhere. */
export function mayOpen(user: Me | null | undefined, pathname: string): boolean {
  const item = navItemFor(pathname);
  return item ? itemAllows(item, user) : allows(user?.role, "viewer");
}

/** Titles for pages that are not in the nav (or are sub-pages with their own name). */
const TITLES: Record<string, string> = {
  "/account": "Account",
  "/spools/new": "Add a spool",
  [NEW_REQUEST_PATH]: "New request",
};

/** The title the phone layout's top bar shows for a path. */
export function pageTitle(pathname: string): string {
  return TITLES[pathname] ?? navItemFor(pathname)?.label ?? "RollCall";
}

/** What the phone layout's bottom bar shows in its centre. */
export type PhoneCentre = "scan" | "new-request" | null;

/** The inventory screens, and their sub-pages: the only pages where Scan shows. */
const INVENTORY_PAGES: ReadonlySet<string> = new Set(["/", "/spools", "/products", "/catalog"]);

/** The bottom bar's centre for a path: New request on the Requests list and a request for
 * someone who can submit, Scan on the inventory screens in the Android app, and nothing
 * anywhere else (the request form's own buttons take the place there). */
export function phoneCentre(user: Me, pathname: string, app: boolean): PhoneCentre {
  if (pathname === NEW_REQUEST_PATH) return null;
  const section = navItemFor(pathname)?.href;
  if (section === "/requests") return canSubmit(user) ? "new-request" : null;
  return app && section !== undefined && INVENTORY_PAGES.has(section) ? "scan" : null;
}

/** The pages anyone may open, and the Admin ones, as the phone menu groups them. */
export function menuGroups(user: Me | null | undefined): { main: NavItem[]; admin: NavItem[] } {
  const items = visibleNav(user);
  return {
    main: items.filter((item) => item.role !== "admin"),
    admin: items.filter((item) => item.role === "admin"),
  };
}
