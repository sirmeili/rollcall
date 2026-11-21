import { render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "#lib/api/client.ts";
import type { Move, Photo } from "#lib/api/requests.ts";
import type { Me } from "#lib/api/types.ts";
import { setTimeZone } from "#lib/format.ts";
import { viewport } from "#lib/viewport.svelte.ts";
import { me } from "../test/fixtures.ts";
import { request } from "../test/request-fixtures.ts";

const nav = vi.hoisted(() => ({
  page: { params: { id: "41" } as Record<string, string>, url: new URL("https://localhost/") },
  goto: vi.fn(),
}));
vi.mock("$app/state", () => ({ page: nav.page }));
vi.mock("$app/navigation", () => ({ goto: nav.goto }));

const api = vi.hoisted(() => ({
  getRequest: vi.fn(),
  moveRequest: vi.fn(),
  uploadPhoto: vi.fn(),
  addPhotos: vi.fn(),
  removePhoto: vi.fn(),
}));
vi.mock("#lib/api/requests.ts", async (original) => ({
  ...(await original<typeof import("#lib/api/requests.ts")>()),
  ...api,
}));

const { session } = await import("#lib/auth/session.svelte.ts");
const DetailPage = (await import("./requests/[id]/+page.svelte")).default;

const FRANK = me("admin", { id: 1, username: "frank" });
const DANA = me("editor", { id: 3, username: "dana" });
const SAM = me("viewer", { id: 2, username: "sam", requester: true, has_requests: true });

const DONE_OR_FAILED: Move[] = [
  { to_status: "done", reason_required: false, photos: true },
  { to_status: "failed", reason_required: false, photos: false },
];

function photo(id: string, name: string): Photo {
  return { id, name, uploaded_at: "2026-11-18T14:00:00Z" };
}

function image(name: string, type = "image/jpeg", size = 1000): File {
  const file = new File(["x"], name, { type });
  Object.defineProperty(file, "size", { value: size });
  return file;
}

function signIn(user: Me): void {
  session.user = user;
  session.loaded = true;
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"], now: new Date("2026-11-18T15:00:00Z") });
  setTimeZone("UTC");
  viewport().phone = false;
  nav.page.params = { id: "41" };
});
afterEach(() => {
  vi.useRealTimers();
  vi.resetAllMocks();
});

async function openDone(): Promise<HTMLElement> {
  signIn(FRANK);
  api.getRequest.mockResolvedValue(request({ status: "printing", moves: DONE_OR_FAILED }));
  render(DetailPage);
  await userEvent.click(await screen.findByRole("button", { name: "Mark Done" }));
  return screen.getByRole("dialog");
}

describe("The Done dialog", () => {
  it("adds photos, uploading them and saving them with the move", async () => {
    const dialog = await openDone();
    api.uploadPhoto.mockImplementation((file: File) =>
      Promise.resolve({ id: `id-${file.name}`, name: file.name }),
    );
    api.moveRequest.mockResolvedValue(
      request({
        status: "done",
        photos: [photo("id-front.jpg", "front.jpg"), photo("id-side.png", "side.png")],
      }),
    );

    await userEvent.upload(within(dialog).getByLabelText("Add photos"), [
      image("front.jpg"),
      image("side.png", "image/png"),
    ]);
    expect(within(dialog).getByText("front.jpg")).toBeVisible();
    expect(within(dialog).getByText("side.png")).toBeVisible();
    await userEvent.click(within(dialog).getByRole("button", { name: "Mark Done" }));

    expect(api.uploadPhoto).toHaveBeenCalledTimes(2);
    expect(api.moveRequest).toHaveBeenCalledWith(41, "printing", "done", "", [
      "id-front.jpg",
      "id-side.png",
    ]);
    expect(screen.queryByRole("dialog")).toBeNull();
    const photos = screen.getByRole("region", { name: "Photos" });
    expect(
      within(photos)
        .getAllByRole("img")
        .map((i) => i.getAttribute("alt")),
    ).toEqual(["front.jpg", "side.png"]);
  });

  it("lets a chosen photo be taken off again", async () => {
    const dialog = await openDone();

    await userEvent.upload(within(dialog).getByLabelText("Add photos"), [image("blurry.jpg")]);
    await userEvent.click(within(dialog).getByRole("button", { name: "Remove blurry.jpg" }));

    expect(within(dialog).queryByText("blurry.jpg")).toBeNull();
  });

  it("takes up to 4 photos", async () => {
    const dialog = await openDone();
    const five = ["a", "b", "c", "d", "e"].map((n) => image(`${n}.jpg`));

    await userEvent.upload(within(dialog).getByLabelText("Add photos"), five);

    expect(within(dialog).getAllByRole("button", { name: /^Remove / })).toHaveLength(4);
    expect(within(dialog).getByText("A request can have up to 4 photos.")).toBeVisible();
    expect(within(dialog).getByLabelText("Add photos")).toBeDisabled();
  });

  it("refuses a file that isn't a JPEG or PNG, or is over 20 MB, before uploading", async () => {
    const dialog = await openDone();
    const input = within(dialog).getByLabelText("Add photos");

    await userEvent.upload(input, [image("print.gif", "image/gif")], { applyAccept: false });
    expect(within(dialog).getByText("print.gif isn't a JPEG or PNG photo.")).toBeVisible();
    await userEvent.upload(input, [image("huge.jpg", "image/jpeg", 21 * 1024 * 1024)]);
    expect(within(dialog).getByText("huge.jpg is over 20 MB.")).toBeVisible();

    expect(within(dialog).queryAllByRole("button", { name: /^Remove / })).toHaveLength(0);
  });

  it("shows why a photo was refused and keeps the request as it was", async () => {
    const dialog = await openDone();
    api.uploadPhoto.mockRejectedValue(
      new ApiError(422, "That isn't a JPEG or PNG photo.", {
        problems: { photo: "That isn't a JPEG or PNG photo." },
      }),
    );

    await userEvent.upload(within(dialog).getByLabelText("Add photos"), [image("fake.jpg")]);
    await userEvent.click(within(dialog).getByRole("button", { name: "Mark Done" }));

    expect(
      await within(dialog).findByText("fake.jpg: That isn't a JPEG or PNG photo."),
    ).toBeVisible();
    expect(api.moveRequest).not.toHaveBeenCalled();
  });

  it("has no Add photos on moves that take none", async () => {
    await openDone();
    await userEvent.keyboard("{Escape}");

    await userEvent.click(screen.getByRole("button", { name: "Mark Failed" }));

    expect(within(screen.getByRole("dialog")).queryByLabelText("Add photos")).toBeNull();
  });
});

describe("The photos section", () => {
  const TWO = [photo("p1", "front.jpg"), photo("p2", "side.png")];

  it.each([
    ["the requester", SAM],
    ["an Editor", DANA],
  ])("shows %s thumbnails that open full size, and nothing to change", async (_who, user) => {
    signIn(user);
    api.getRequest.mockResolvedValue(request({ status: "done", photos: TWO }));
    render(DetailPage);

    const photos = await screen.findByRole("region", { name: "Photos" });
    const links = within(photos).getAllByRole("link");
    expect(links.map((a) => a.getAttribute("href"))).toEqual([
      "/api/v1/requests/41/photos/p1",
      "/api/v1/requests/41/photos/p2",
    ]);
    expect(links[0]).toHaveAttribute("target", "_blank");
    expect(within(links[0]).getByRole("img")).toHaveAttribute(
      "src",
      "/api/v1/requests/41/photos/p1",
    );
    expect(within(photos).queryByRole("button")).toBeNull();
    expect(within(photos).queryByLabelText("Add photos")).toBeNull();
  });

  it("is left out when there are no photos and the caller can't add any", async () => {
    signIn(SAM);
    api.getRequest.mockResolvedValue(request({ status: "done" }));
    render(DetailPage);

    await screen.findByRole("heading", { name: "Wingspan insert" });
    expect(screen.queryByRole("region", { name: "Photos" })).toBeNull();
  });

  it("lets an Admin add photos while the request is Done or Picked Up", async () => {
    signIn(FRANK);
    api.getRequest.mockResolvedValue(
      request({ status: "picked_up", photos: [], can_change_photos: true }),
    );
    api.uploadPhoto.mockResolvedValue({ id: "p3", name: "later.jpg" });
    api.addPhotos.mockResolvedValue(
      request({ status: "picked_up", photos: [photo("p3", "later.jpg")], can_change_photos: true }),
    );
    render(DetailPage);

    const photos = await screen.findByRole("region", { name: "Photos" });
    expect(within(photos).getByText("No photos yet.")).toBeVisible();
    await userEvent.upload(within(photos).getByLabelText("Add photos"), [image("later.jpg")]);

    expect(api.addPhotos).toHaveBeenCalledWith(41, ["p3"]);
    expect(await within(photos).findByRole("img", { name: "later.jpg" })).toBeVisible();
  });

  it("lets an Admin remove a photo", async () => {
    signIn(FRANK);
    api.getRequest.mockResolvedValue(
      request({ status: "done", photos: TWO, can_change_photos: true }),
    );
    api.removePhoto.mockResolvedValue(
      request({ status: "done", photos: [TWO[0]], can_change_photos: true }),
    );
    render(DetailPage);

    const photos = await screen.findByRole("region", { name: "Photos" });
    await userEvent.click(within(photos).getByRole("button", { name: "Remove side.png" }));

    expect(api.removePhoto).toHaveBeenCalledWith(41, "p2");
    expect(within(photos).queryByRole("img", { name: "side.png" })).toBeNull();
  });

  it("says why a photo wasn't removed", async () => {
    signIn(FRANK);
    api.getRequest.mockResolvedValue(
      request({ status: "done", photos: TWO, can_change_photos: true }),
    );
    api.removePhoto.mockRejectedValue(new ApiError(0, "The connection dropped"));
    render(DetailPage);

    const photos = await screen.findByRole("region", { name: "Photos" });
    await userEvent.click(within(photos).getByRole("button", { name: "Remove side.png" }));

    expect(await within(photos).findByRole("alert")).toBeVisible();
    expect(within(photos).getByRole("img", { name: "side.png" })).toBeVisible();
  });

  it("offers no Add photos once a request has 4", async () => {
    signIn(FRANK);
    const four = ["a", "b", "c", "d"].map((n) => photo(n, `${n}.jpg`));
    api.getRequest.mockResolvedValue(
      request({ status: "done", photos: four, can_change_photos: true }),
    );
    render(DetailPage);

    const photos = await screen.findByRole("region", { name: "Photos" });
    expect(within(photos).getAllByRole("button", { name: /^Remove / })).toHaveLength(4);
    expect(within(photos).queryByLabelText("Add photos")).toBeNull();
  });

  it("shows why an added photo was refused", async () => {
    signIn(FRANK);
    api.getRequest.mockResolvedValue(
      request({ status: "done", photos: [], can_change_photos: true }),
    );
    api.uploadPhoto.mockRejectedValue(
      new ApiError(422, "That photo is too large. Use one under 40 megapixels."),
    );
    render(DetailPage);

    const photos = await screen.findByRole("region", { name: "Photos" });
    await userEvent.upload(within(photos).getByLabelText("Add photos"), [image("pano.jpg")]);

    expect(
      await within(photos).findByText(
        "pano.jpg: That photo is too large. Use one under 40 megapixels.",
      ),
    ).toBeVisible();
    expect(api.addPhotos).not.toHaveBeenCalled();
  });
});

describe("Photo history", () => {
  it("says who added and removed a photo, and which", async () => {
    signIn(SAM);
    api.getRequest.mockResolvedValue(
      request({
        status: "done",
        history: [
          {
            kind: "photo_removed",
            username: "frank",
            at: "2026-11-18T14:30:00Z",
            fields: null,
            from_value: null,
            to_value: null,
            note: "blurry.jpg",
            automatic: false,
          },
          {
            kind: "photo_added",
            username: "frank",
            at: "2026-11-18T14:00:00Z",
            fields: null,
            from_value: null,
            to_value: null,
            note: "blurry.jpg",
            automatic: false,
          },
        ],
      }),
    );
    render(DetailPage);

    expect(await screen.findByText("Photo removed by frank")).toBeVisible();
    expect(screen.getByText("Photo added by frank")).toBeVisible();
    expect(screen.getAllByText("blurry.jpg")).toHaveLength(2);
  });
});
