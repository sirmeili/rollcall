/** Calls for print requests (server/src/filament_tracker/api/requests.py). */

import {
  accessHeaders,
  api,
  ApiError,
  apiUrl,
  CSRF_HEADER,
  errorMessage,
  parseAnswer,
} from "#lib/api/client.ts";
import type { SimilarColor } from "#lib/api/catalog.ts";

export type Priority = "urgent" | "normal" | "no_rush";
export type RequestStatus =
  | "submitted"
  | "approved"
  | "waiting_on_filament"
  | "queued"
  | "printing"
  | "done"
  | "picked_up"
  | "rejected"
  | "cancelled"
  | "failed";
export type ModelKind = "3mf" | "stl";
/** What a request has for its model; "notes" when only its notes say where it is. */
export type ModelSource = "file" | "link" | "both" | "notes";

export interface Requester {
  id: number;
  username: string;
}

export interface Swatch {
  name: string;
  /** RRGGBB, the main color first. */
  hexes: string[];
}

export interface RequestRow {
  id: number;
  title: string;
  quantity: number;
  /** YYYY-MM-DD */
  needed_by: string | null;
  priority: Priority;
  status: RequestStatus;
  requester: Requester;
  model: ModelSource;
  choices: Swatch[];
  created_at: string;
}

export interface ModelFile {
  name: string;
  size: number;
  kind: ModelKind;
  /** Not on the server's disk (say, after a restore onto a fresh volume). */
  missing: boolean;
}

/** Grams held on one spool for a filament choice. */
export interface Hold {
  spool_id: number;
  product_id: number;
  product_name: string;
  grams: number;
}

/** One filament choice, with the stock and catalog as they are now. */
export interface Choice {
  /** Names the choice in Approve's grams. */
  id: number;
  kind: "product" | "catalog_color";
  note: string;
  /** The product's name, or the catalog color's name and line. */
  name: string;
  hexes: string[];
  material: string | null;
  product_id: number | null;
  sealed: number | null;
  open: number | null;
  catalog_color: string | null;
  /** A catalog color's own name ("Black") and its filament line's ("PLA Basic"). */
  color_name: string | null;
  line: string | null;
  bambu_code: string | null;
  /** False: the catalog has dropped it since it was chosen. */
  in_catalog: boolean;
  multi_color: boolean;
  similar: SimilarColor[];
  /** Held in full, while the request is Approved, Waiting on Filament or Queued; else null.
   * The only word on holds a requester gets. */
  held: boolean | null;
  /** The rest are for Editors and Admins only, and null for anyone else. The grams for the
   * whole quantity, from Approve (null until then). */
  grams: number | null;
  /** Grams not yet held, while the request is Approved, Waiting on Filament or Queued. */
  short_g: number | null;
  holds: Hold[] | null;
  /** Grams not held of the product it would be held on (0 with none). */
  available_g: number | null;
}

export type HistoryKind =
  "submitted" | "edited" | "priority_changed" | "status_changed" | "photo_added" | "photo_removed";

export interface HistoryEntry {
  kind: HistoryKind;
  username: string | null;
  at: string;
  /** An edit's changed fields. */
  fields: string[] | null;
  /** A priority change's old and new priority, or a status change's old and new status. */
  from_value: string | null;
  to_value: string | null;
  /** The note or reason, or the name of a photo added or removed. */
  note: string | null;
  /** Made by RollCall itself, with no one, such as the move on after Approve. */
  automatic: boolean;
}

/** A move the caller may make now. */
export interface Move {
  to_status: RequestStatus;
  /** Its note is a reason, which may not be left empty. */
  reason_required: boolean;
  /** Up to 4 photos of the finished print may be saved with it. */
  photos: boolean;
}

/** A photo of the finished print. */
export interface Photo {
  id: string;
  name: string;
  uploaded_at: string;
}

/** A photo uploaded and waiting to be saved with a request. */
export interface PhotoUpload {
  id: string;
  name: string;
}

export interface PrintRequest {
  id: number;
  title: string;
  notes: string;
  quantity: number;
  needed_by: string | null;
  priority: Priority;
  link: string | null;
  status: RequestStatus;
  requester: Requester;
  file: ModelFile | null;
  /** Oldest first. */
  photos: Photo[];
  choices: Choice[];
  /** Newest first. */
  history: HistoryEntry[];
  created_at: string;
  updated_at: string;
  can_edit: boolean;
  can_change_priority: boolean;
  /** Add and remove photos: a signed-in Admin, while the request is Done or Picked Up. */
  can_change_photos: boolean;
  /** The moves the caller may make, the main next step first. */
  moves: Move[];
  /** Which try at printing it this is: 1, plus 1 for each Reprint. */
  attempt: number;
  /** The store Find in store searches. */
  store_address: string;
}

/** A filament choice as sent: a product or a catalog color (its UUID). */
export type ChoiceIn =
  { product_id: number; note: string } | { catalog_color: string; note: string };

export interface RequestIn {
  title: string;
  notes: string;
  quantity: number;
  needed_by: string | null;
  priority: Priority;
  link: string | null;
  choices: ChoiceIn[];
  /** A finished upload to save as the model file, replacing any file it has. */
  upload_id: string | null;
}

export interface RequestEdit extends RequestIn {
  remove_file: boolean;
}

export interface Upload {
  id: string;
  name: string;
  size: number;
  kind: ModelKind;
}

/** Active holds every open status; Closed holds Picked Up, Rejected and Cancelled. */
export type RequestTab = "active" | "closed";

export interface RequestQuery {
  tab: RequestTab;
  /** Open statuses to keep; none keeps them all. Only Editors and Admins filter. */
  statuses: RequestStatus[];
  /** Only the caller's own requests. */
  mine: boolean;
}

/** The query string for `GET /requests`, leaving out filters that are off. */
export function requestQuery(query: RequestQuery): string {
  const params = new URLSearchParams({ tab: query.tab });
  for (const status of query.statuses) params.append("status", status);
  if (query.mine) params.set("mine", "true");
  return `?${params.toString()}`;
}

export function listRequests(query?: RequestQuery, signal?: AbortSignal): Promise<RequestRow[]> {
  return api<RequestRow[]>(`/requests${query ? requestQuery(query) : ""}`, { signal });
}

export function getRequest(id: number): Promise<PrintRequest> {
  return api<PrintRequest>(`/requests/${id}`);
}

export function submitRequest(body: RequestIn): Promise<PrintRequest> {
  return api<PrintRequest>("/requests", { method: "POST", body });
}

export function editRequest(id: number, body: RequestEdit): Promise<PrintRequest> {
  return api<PrintRequest>(`/requests/${id}`, { method: "PATCH", body });
}

export function changePriority(id: number, priority: Priority): Promise<PrintRequest> {
  return api<PrintRequest>(`/requests/${id}/priority`, { method: "POST", body: { priority } });
}

/** Move a request to another status, with any photo uploads for a move that takes them.
 * `from` is the status the caller saw it in: if it has moved since, this fails with 409. */
export function moveRequest(
  id: number,
  from: RequestStatus,
  to: RequestStatus,
  note: string,
  photoIds: string[] = [],
  grams?: Record<number, number>,
): Promise<PrintRequest> {
  const body = { from_status: from, to_status: to, note, photo_ids: photoIds };
  return api<PrintRequest>(`/requests/${id}/moves`, {
    method: "POST",
    body: grams ? { ...body, grams } : body,
  });
}

/** Save photo uploads with a Done or Picked Up request. */
export function addPhotos(id: number, photoIds: string[]): Promise<PrintRequest> {
  return api<PrintRequest>(`/requests/${id}/photos`, {
    method: "POST",
    body: { photo_ids: photoIds },
  });
}

/** Remove a photo from a Done or Picked Up request. */
export function removePhoto(id: number, photoId: string): Promise<PrintRequest> {
  return api<PrintRequest>(`/requests/${id}/photos/${photoId}`, { method: "DELETE" });
}

/** Where a request's photo is shown from, full size. */
export function photoUrl(id: number, photoId: string): string {
  return apiUrl(`/requests/${id}/photos/${photoId}`);
}

/** Submitted requests, for the Requests link (Editors and Admins). */
export async function submittedCount(): Promise<number> {
  return (await api<{ submitted: number }>("/requests/count")).submitted;
}

/** Where a request's model file downloads from. */
export function fileUrl(id: number): string {
  return apiUrl(`/requests/${id}/file`);
}

/** The field problems a refused request comes back with (422), or null. */
export function problemsOf(error: unknown): Record<string, string> | null {
  if (!(error instanceof ApiError) || error.status !== 422) return null;
  const detail = error.detail;
  if (detail && typeof detail === "object" && "problems" in detail) {
    return (detail as { problems: Record<string, string> }).problems;
  }
  return null;
}

export interface UploadHandle<T = Upload> {
  done: Promise<T>;
  cancel: () => void;
}

/** Send a file as the request body to `path`, reporting progress (0 to 100). XMLHttpRequest
 * rather than fetch, because only it reports upload progress. A refusal's message is the
 * problem named `field`, if there is one. */
function sendFile<T>(
  path: string,
  file: File,
  field: string,
  onprogress: (percent: number) => void,
  Xhr: typeof XMLHttpRequest,
): UploadHandle<T> {
  const xhr = new Xhr();
  const url = apiUrl(`${path}?name=${encodeURIComponent(file.name)}`);
  const done = new Promise<T>((resolve, reject) => {
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onprogress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      const body = parseAnswer(xhr.responseText);
      if (xhr.status >= 200 && xhr.status < 300) return resolve(body as T);
      const detail =
        body && typeof body === "object" ? (body as { detail?: unknown }).detail : undefined;
      const problems =
        detail && typeof detail === "object" && "problems" in detail
          ? (detail as { problems: Record<string, string> }).problems
          : null;
      const message = problems?.[field] ?? errorMessage(body, `Upload failed (${xhr.status})`);
      reject(new ApiError(xhr.status, message, detail));
    };
    xhr.onerror = () => reject(new ApiError(0, "The connection dropped"));
    xhr.onabort = () => reject(new ApiError(0, "Upload cancelled"));
  });
  xhr.open("POST", url);
  xhr.withCredentials = true;
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/octet-stream",
    ...CSRF_HEADER,
    ...accessHeaders(url),
  };
  for (const [name, value] of Object.entries(headers)) xhr.setRequestHeader(name, value);
  xhr.send(file);
  return { done, cancel: () => xhr.abort() };
}

/** Upload a model file as the request body, reporting progress (0 to 100). */
export function uploadModel(
  file: File,
  onprogress: (percent: number) => void,
  Xhr: typeof XMLHttpRequest = XMLHttpRequest,
): UploadHandle {
  return sendFile<Upload>("/requests/uploads", file, "file", onprogress, Xhr);
}

/** Upload a photo of the finished print (an Admin), to save with the Done move or with a
 * Done or Picked Up request. */
export function uploadPhoto(
  file: File,
  Xhr: typeof XMLHttpRequest = XMLHttpRequest,
): Promise<PhotoUpload> {
  return sendFile<PhotoUpload>("/requests/photo-uploads", file, "photo", () => {}, Xhr).done;
}
