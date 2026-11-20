import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "#lib/api/client.ts";
import {
  addPhotos,
  changePriority,
  editRequest,
  fileUrl,
  getRequest,
  listRequests,
  moveRequest,
  photoUrl,
  problemsOf,
  removePhoto,
  submitRequest,
  submittedCount,
  uploadModel,
  uploadPhoto,
  type RequestEdit,
} from "#lib/api/requests.ts";
import { fakeFetch } from "../../test/fixtures.ts";

afterEach(() => vi.unstubAllGlobals());

describe("the request calls", () => {
  it("list, read, submit, edit and reprioritise requests", async () => {
    const body = { title: "Lamp" } as RequestEdit;
    const fetch = fakeFetch({
      "GET /requests": [],
      "GET /requests/41": { id: 41 },
      "POST /requests": { id: 42 },
      "PATCH /requests/41": { id: 41 },
      "POST /requests/41/priority": { id: 41 },
      "GET /requests/count": { submitted: 3 },
    });
    vi.stubGlobal("fetch", fetch);

    await listRequests();
    await getRequest(41);
    await submitRequest(body);
    await editRequest(41, body);
    await changePriority(41, "urgent");
    expect(await submittedCount()).toBe(3);

    expect(fetch.calls.map((c) => [c.method, c.path, c.body])).toEqual([
      ["GET", "/requests", undefined],
      ["GET", "/requests/41", undefined],
      ["POST", "/requests", body],
      ["PATCH", "/requests/41", body],
      ["POST", "/requests/41/priority", { priority: "urgent" }],
      ["GET", "/requests/count", undefined],
    ]);
    expect(fileUrl(41)).toMatch(/\/api\/v1\/requests\/41\/file$/);
  });

  it("list a tab with the status filter and Only mine, leaving out what is off", async () => {
    const fetch = fakeFetch({
      "GET /requests?tab=closed": [],
      "GET /requests?tab=active&status=queued&status=failed&mine=true": [],
    });
    vi.stubGlobal("fetch", fetch);

    await listRequests({ tab: "closed", statuses: [], mine: false });
    await listRequests({ tab: "active", statuses: ["queued", "failed"], mine: true });

    expect(fetch.calls.map((c) => c.path)).toEqual([
      "/requests?tab=closed",
      "/requests?tab=active&status=queued&status=failed&mine=true",
    ]);
  });
});

/** Stands in for XMLHttpRequest: records what is sent, and the test answers. */
class FakeXhr {
  static last: FakeXhr;
  method = "";
  url = "";
  headers: Record<string, string> = {};
  body: unknown = null;
  withCredentials = false;
  status = 0;
  responseText = "";
  upload: { onprogress: ((event: ProgressEvent) => void) | null } = { onprogress: null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;
  abort = vi.fn(() => this.onabort?.());

  constructor() {
    FakeXhr.last = this;
  }

  open(method: string, url: string): void {
    this.method = method;
    this.url = url;
  }

  setRequestHeader(name: string, value: string): void {
    this.headers[name] = value;
  }

  send(body: unknown): void {
    this.body = body;
  }

  answer(status: number, body: unknown): void {
    this.status = status;
    this.responseText = JSON.stringify(body);
    this.onload?.();
  }
}

const Xhr = FakeXhr as unknown as typeof XMLHttpRequest;

function start(onprogress = vi.fn()) {
  const file = new File(["solid part"], "my part.stl");
  const handle = uploadModel(file, onprogress, Xhr);
  return { file, handle, xhr: FakeXhr.last, onprogress };
}

describe("uploadModel", () => {
  it("sends the file as the body, named in the address, with the CSRF header", async () => {
    const { file, handle, xhr } = start();

    expect(xhr.method).toBe("POST");
    expect(xhr.url).toMatch(/\/requests\/uploads\?name=my%20part\.stl$/);
    expect(xhr.body).toBe(file);
    expect(xhr.withCredentials).toBe(true);
    expect(xhr.headers).toMatchObject({
      "Content-Type": "application/octet-stream",
      "X-Requested-With": "filament-tracker",
    });
    xhr.answer(201, { id: "u1", name: "my part.stl", size: 10, kind: "stl" });
    await expect(handle.done).resolves.toEqual({
      id: "u1",
      name: "my part.stl",
      size: 10,
      kind: "stl",
    });
  });

  it("reports progress as a percentage", () => {
    const { xhr, onprogress } = start();

    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 38, total: 100 } as ProgressEvent);
    xhr.upload.onprogress?.({ lengthComputable: false, loaded: 1, total: 0 } as ProgressEvent);

    expect(onprogress.mock.calls).toEqual([[38]]);
  });

  it("rejects with the server's message about the file", async () => {
    const { handle, xhr } = start();

    xhr.answer(422, { detail: { problems: { file: "That isn't a 3MF or STL file." } } });

    await expect(handle.done).rejects.toMatchObject({
      status: 422,
      message: "That isn't a 3MF or STL file.",
    });
  });

  it("rejects with any other refusal", async () => {
    const { handle, xhr } = start();

    xhr.answer(413, { detail: "request body too large" });

    await expect(handle.done).rejects.toMatchObject({ status: 413 });
  });

  it("rejects when the connection drops or it is cancelled", async () => {
    const dropped = start();
    dropped.xhr.onerror?.();
    await expect(dropped.handle.done).rejects.toMatchObject({ status: 0 });

    const cancelled = start();
    cancelled.handle.cancel();
    expect(cancelled.xhr.abort).toHaveBeenCalled();
    await expect(cancelled.handle.done).rejects.toMatchObject({ message: "Upload cancelled" });
  });
});

describe("problemsOf", () => {
  it("reads the field problems from a refused request only", () => {
    const problems = { title: "Enter a title." };
    expect(problemsOf(new ApiError(422, "x", { problems }))).toEqual(problems);
    expect(problemsOf(new ApiError(422, "x", "plain"))).toBeNull();
    expect(problemsOf(new ApiError(400, "x", { problems }))).toBeNull();
    expect(problemsOf(new Error("x"))).toBeNull();
  });
});

describe("the photo calls", () => {
  it("move to Done with photos, add them later, remove one, and show one", async () => {
    const fetch = fakeFetch({
      "POST /requests/41/moves": { id: 41 },
      "POST /requests/41/photos": { id: 41 },
      "DELETE /requests/41/photos/p1": { id: 41 },
    });
    vi.stubGlobal("fetch", fetch);

    await moveRequest(41, "printing", "done", "", ["p1"]);
    await addPhotos(41, ["p2"]);
    await removePhoto(41, "p1");

    expect(fetch.calls.map((c) => [c.method, c.path, c.body])).toEqual([
      [
        "POST",
        "/requests/41/moves",
        { from_status: "printing", to_status: "done", note: "", photo_ids: ["p1"] },
      ],
      ["POST", "/requests/41/photos", { photo_ids: ["p2"] }],
      ["DELETE", "/requests/41/photos/p1", undefined],
    ]);
    expect(photoUrl(41, "p1")).toMatch(/\/api\/v1\/requests\/41\/photos\/p1$/);
  });

  it("uploads a photo as the body, and rejects with the server's message about it", async () => {
    const file = new File(["jpeg"], "front.jpg", { type: "image/jpeg" });
    const done = uploadPhoto(file, Xhr);
    const xhr = FakeXhr.last;
    expect(xhr.url).toMatch(/\/requests\/photo-uploads\?name=front\.jpg$/);
    expect(xhr.body).toBe(file);
    xhr.answer(201, { id: "p1", name: "front.jpg" });
    await expect(done).resolves.toEqual({ id: "p1", name: "front.jpg" });

    const refused = uploadPhoto(file, Xhr);
    FakeXhr.last.answer(422, {
      detail: { problems: { photo: "That isn't a JPEG or PNG photo." } },
    });
    await expect(refused).rejects.toMatchObject({ message: "That isn't a JPEG or PNG photo." });
  });
});
