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
  /** The Account switches: emails about one's own requests, and (Admins) about new ones. */
  email_on_request_change: boolean;
  email_on_new_request: boolean;
  /** Whether this server can send email at all (an SMTP host is saved). */
  email_set_up: boolean;
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

export interface SpoolDetail extends SpoolRow {
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

export interface ReviewOut {
  flagged_events: EventOut[];
  unidentified_tags: UnidentifiedTag[];
  likely_empty: SpoolRow[];
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
