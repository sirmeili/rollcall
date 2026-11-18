/** The request form's fields and the rules it checks before sending. The server checks
 * the same rules (server/src/filament_tracker/print_requests/rules.py). */

import type { PrintRequest, Priority, RequestEdit, RequestIn, Upload } from "#lib/api/requests.ts";
import { choiceIn, chosenFrom, type Chosen } from "#lib/requests/picker.ts";
import { sizeText } from "#lib/requests/labels.ts";

export const TITLE_MAX = 120;
export const NOTES_MAX = 2000;
export const NOTE_MAX = 80;
export const LINK_MAX = 2000;
export const MAX_MODEL_BYTES = 95 * 1024 * 1024;

/** The model file on the form. */
export type FileState =
  | { status: "none" }
  /** The file the request already has; missing when it is no longer on the server's disk. */
  | { status: "kept"; name: string; size: number; missing: boolean }
  | { status: "uploading"; name: string; size: number; percent: number }
  | { status: "failed"; name: string; size: number; percent: number; message: string }
  | { status: "uploaded"; upload: Upload };

export interface RequestForm {
  title: string;
  /** As typed. */
  quantity: string;
  priority: Priority;
  /** YYYY-MM-DD, or "" for none. */
  neededBy: string;
  link: string;
  notes: string;
  file: FileState;
  choices: Chosen[];
}

export type FormField = "title" | "quantity" | "needed_by" | "file" | "link" | "notes" | "choices";

export interface FormProblem {
  field: FormField;
  message: string;
}

export function blankForm(): RequestForm {
  return {
    title: "",
    quantity: "1",
    priority: "normal",
    neededBy: "",
    link: "",
    notes: "",
    file: { status: "none" },
    choices: [],
  };
}

export function formFrom(request: PrintRequest): RequestForm {
  return {
    title: request.title,
    quantity: String(request.quantity),
    priority: request.priority,
    neededBy: request.needed_by ?? "",
    link: request.link ?? "",
    notes: request.notes,
    file: request.file
      ? {
          status: "kept",
          name: request.file.name,
          size: request.file.size,
          missing: request.file.missing,
        }
      : { status: "none" },
    choices: request.choices.map(chosenFrom),
  };
}

/** Why a picked file can't be a request's model, or null. */
export function fileProblem(name: string, size: number): string | null {
  if (!/\.(3mf|stl)$/i.test(name)) {
    return `${name} isn't a 3MF or STL file. Choose a .3mf or .stl file.`;
  }
  if (size > MAX_MODEL_BYTES) return `${name} is ${sizeText(size)}. Files can be up to 95 MB.`;
  return null;
}

export function isWebLink(text: string): boolean {
  try {
    const url = new URL(text);
    return (url.protocol === "http:" || url.protocol === "https:") && url.hostname !== "";
  } catch {
    return false;
  }
}

/** A file that counts as the model: an upload, or the request's own file while it is on
 * disk. */
export function hasFile(file: FileState): boolean {
  return (file.status === "kept" && !file.missing) || file.status === "uploaded";
}

/** Everything to fix before sending, in the order of the form. An edit meets the same
 * rules as a new request. */
export function formProblems(form: RequestForm, today: string): FormProblem[] {
  const problems: FormProblem[] = [];
  const add = (field: FormField, message: string) => problems.push({ field, message });
  if (!form.title.trim()) add("title", "Enter a title.");
  const quantity = Number(form.quantity);
  if (!/^\d+$/.test(form.quantity.trim()) || quantity < 1 || quantity > 100) {
    add("quantity", "Enter a quantity from 1 to 100.");
  }
  if (form.neededBy && form.neededBy < today) {
    add("needed_by", "Needed by can't be in the past. Pick today or later, or leave it empty.");
  }
  if (form.file.status === "uploading") {
    add("file", `${form.file.name} is still uploading. Wait for it to finish, or cancel it.`);
  } else if (form.file.status === "failed") {
    add("file", `${form.file.name} didn't upload. Try again, or remove it.`);
  }
  const link = form.link.trim();
  if (link && !isWebLink(link)) add("link", "Enter a link that starts with http:// or https://.");
  if (!hasFile(form.file) && !link && !form.notes.trim()) {
    add("notes", "Add a file or a link, or say in the notes where the model is.");
  }
  if (form.choices.length === 0) add("choices", "Add at least one filament.");
  return problems;
}

/** The form as the API takes a new request. */
export function requestBody(form: RequestForm): RequestIn {
  return {
    title: form.title.trim(),
    notes: form.notes.trim(),
    quantity: Number(form.quantity),
    needed_by: form.neededBy || null,
    priority: form.priority,
    link: form.link.trim() || null,
    choices: form.choices.map(choiceIn),
    upload_id: form.file.status === "uploaded" ? form.file.upload.id : null,
  };
}

/** The form as the API takes an edit: a request whose file was removed loses it. */
export function editBody(form: RequestForm): RequestEdit {
  return { ...requestBody(form), remove_file: form.file.status === "none" };
}

/** "Fix 2 things before submitting" */
export function summaryHeading(count: number, editing: boolean): string {
  const things = count === 1 ? "1 thing" : `${count} things`;
  return `Fix ${things} before ${editing ? "saving" : "submitting"}`;
}
