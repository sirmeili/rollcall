import type { Role } from "#lib/roles.ts";

/** The signed-in user (`GET /auth/me`). */
export interface UserBase {
  id: number;
  username: string;
  role: Role;
  /** May submit print requests, alongside the role (ADR-0017). */
  requester: boolean;
  /** Optional and never verified. */
  email: string | null;
}

export interface Me extends UserBase {
  /** The server's time zone: the web app shows every time in it. */
  time_zone: string;
  /** Has made a print request, so keeps the Requests page after Requester is turned off. */
  has_requests: boolean;
  /** Notification settings for each kind the user's role can see, in the order to list them. */
  notifications: NotificationSetting[];
  /** Whether this server can send email at all (an SMTP host is saved). */
  email_set_up: boolean;
  /** Whether the user has a phone registered for phone notifications. */
  phone_registered: boolean;
}

/** What a notification is about: server/src/filament_tracker/notifications/kinds.py. */
export type NotificationKind =
  | "new_request"
  | "request_update"
  | "new_photo"
  | "low_stock"
  | "suggestion"
  | "nearly_out"
  | "backup_failed";

/** How a notification reaches a person. */
export type NotificationChannel = "email" | "phone";

/** A user's own choice for one kind on one channel. */
export interface NotificationChoice {
  kind: NotificationKind;
  channel: NotificationChannel;
  on: boolean;
}

export interface NotificationSetting extends NotificationChoice {
  /** The user hasn't chosen: `on` is the kind's default for them. */
  default: boolean;
}

/** Response bodies from server/src/filament_tracker/api/read_schemas.py. */

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

/** A product's tie to its catalog color. The color's fields are null when it is no longer
 * in the catalog (a manual link to a color the catalog dropped). */
export interface CatalogLink {
  uuid: string | null;
  name: string | null;
  /** The filament line, such as PLA Basic. */
  line: string | null;
  /** RRGGBB, the main color first. */
  hexes: string[] | null;
  bambu_code: string | null;
  /** tag: automatic, from its tag; hand: set by a person. */
  how: "tag" | "hand";
  in_catalog: boolean;
  /** For a manual link: who set it, and when. */
  linked_by: string | null;
  linked_at: string | null;
  /** No longer in the catalog: the line and color it was. */
  was_line: string | null;
  was_name: string | null;
  /** The product's tag gives a catalog color, which clearing a manual link goes back to. */
  tag_link_exists: boolean;
}

export interface Product {
  id: number;
  display_name: string;
  filament_type: string;
  /** RRGGBBAA */
  color_rgba: string;
  material_id: string | null;
  variant_id: string | null;
  low_stock_threshold: number;
  nearly_out_pct: number;
  provisional: boolean;
  /** Made from an AMS report rather than by hand. */
  from_ams: boolean;
  /** Made from a catalog color put on the shopping list, until a tag fills it in. */
  from_catalog: boolean;
  /** Its catalog color; null when it has none. */
  catalog_link: CatalogLink | null;
}

export interface Counts {
  sealed: number;
  open: number;
  empty: number;
  unknown: number;
}

export interface OpenSpool {
  id: number;
  remaining_pct: number | null;
  nearly_out: boolean;
}

/** One inventory card. */
export interface ProductSummary {
  product: Product;
  counts: Counts;
  low_stock: boolean;
  open_spools: OpenSpool[];
  /** About how many grams of its Sealed and Open spools are not held, leaving out spools
   * whose grams are unknown. */
  available_g: number;
  /** An Open spool's grams are unknown. */
  available_unknown: boolean;
}

export type SpoolState = "sealed" | "open" | "empty" | "unknown";

/** Where a spool is loaded. Indexes are 0-based; show them as AMS 1, slot 1. */
export interface AmsSlotRef {
  printer_id: number;
  printer_name: string;
  ams_index: number;
  tray_index: number;
}

export interface SpoolRow {
  id: number;
  state: SpoolState;
  product: Product;
  placeholder: boolean;
  location: string | null;
  remaining_pct: number | null;
  /** Grams of filament when full */
  net_weight_g: number | null;
  /** About how many grams are left; null when unknown */
  grams_left_g: number | null;
  received_at: string | null;
  opened_at: string | null;
  emptied_at: string | null;
  ams_slot: AmsSlotRef | null;
}

export interface TagOut {
  uid: string;
  first_seen_at: string;
  decoded: Record<string, unknown> | null;
  decoder_version: number | null;
}

export interface EventOut {
  id: string;
  spool_id: number;
  product_name: string;
  color_rgba: string;
  type: "received" | "opened" | "empty" | "revert" | string;
  source: string;
  occurred_at: string;
  recorded_at: string;
  flagged: boolean;
  device_id: string | null;
  device_name: string | null;
  username: string | null;
  reverts: string | null;
  reverted_by: string | null;
  can_undo: boolean;
  reviewed_at: string | null;
  reviewed_by: string | null;
}

/** A request holding a spool. */
export interface HoldingRequest {
  id: number;
  title: string;
}

export interface SpoolDetail extends SpoolRow {
  /** Grams held for requests. */
  held_g: number;
  /** About how many grams are not held, never below 0; null if unknown. */
  available_g: number | null;
  /** Held beyond its grams left, leaving out holds of Printing requests. */
  over_held: boolean;
  /** The requests holding it; Editors and Admins only, else null. */
  holding_requests: HoldingRequest[] | null;
  notes: string | null;
  tags: TagOut[];
  /** Newest first */
  events: EventOut[];
}

export type EventSource = "scanner" | "ui" | "ams";

export interface UnidentifiedTag {
  uid: string;
  first_seen_at: string;
  /** False if the tag's blocks could not be decoded */
  readable: boolean;
  decoded: Record<string, unknown> | null;
}

/** A product a scan made that may be the same as a "From the catalog" product. */
export interface PossibleDuplicate {
  id: number;
  /** The product the scan made. */
  product: Product;
  /** The "From the catalog" products it may be the same as, oldest first. */
  candidates: Product[];
  created_at: string;
}

export interface ReviewOut {
  flagged_events: EventOut[];
  unidentified_tags: UnidentifiedTag[];
  likely_empty: SpoolRow[];
  possible_duplicates: PossibleDuplicate[];
}

export interface DeviceOut {
  id: string;
  name: string;
  created_at: string;
  last_seen_at: string | null;
  fw_version: string | null;
  queue_length: number | null;
  online: boolean;
  revoked: boolean;
  /** The user a phone belongs to; null for a shared scanner. */
  owner?: string | null;
  /** Revoked and no event names it, so it can be deleted. */
  deletable: boolean;
}

/** A device with its token, shown once. */
export interface DeviceCreated extends DeviceOut {
  token: string;
}

export interface UserOut extends UserBase {
  disabled: boolean;
  created_at: string;
  last_login_at: string | null;
}

export type ManualAction = "received" | "opened" | "empty";

export interface ActionResult {
  outcome: "applied" | "already_in_state" | "flagged";
  event: EventOut;
  spool: SpoolDetail;
}

export type PrinterConnection =
  "starting" | "connected" | "disconnected" | "pin_mismatch" | "not_configured";

export interface SlotOut {
  ams_index: number;
  tray_index: number;
  filament_type: string | null;
  color_rgba: string | null;
  remaining_pct: number | null;
  spool: { id: number; state: SpoolState; product: Product } | null;
  updated_at: string;
}

export interface PrinterOut {
  id: number;
  name: string;
  host: string;
  port: number;
  /** The printer's serial, or the alias an MQTT proxy uses. */
  serial: string;
  /** False without a usable access code: the server is not connecting. */
  configured: boolean;
  /** Whether an access code is saved. The code itself is never sent back. */
  access_code_set: boolean;
  /** A saved access code the server's key cannot open: it needs entering again. */
  access_code_unreadable: boolean;
  connection: PrinterConnection;
  online: boolean;
  last_report_at: string | null;
  pinned_sha256: string | null;
  presented_sha256: string | null;
  slots: SlotOut[];
}
