/** Photos of a finished print, checked here before uploading; the server checks again by
 * their contents. */

import { describeError } from "#lib/api/errors.ts";
import { uploadPhoto } from "#lib/api/requests.ts";

export const MAX_PHOTOS = 4;
export const MAX_PHOTO_BYTES = 20 * 1024 * 1024;
export const PHOTO_TYPES = ["image/jpeg", "image/png"];
export const TOO_MANY_PHOTOS = `A request can have up to ${MAX_PHOTOS} photos.`;

/** Why a chosen file can't be a photo, or null. */
export function photoProblem(file: File): string | null {
  if (!PHOTO_TYPES.includes(file.type)) return `${file.name} isn't a JPEG or PNG photo.`;
  if (file.size > MAX_PHOTO_BYTES) return `${file.name} is over 20 MB.`;
  return null;
}

/** The chosen files that fit beside `kept` photos, and what was said about the rest. */
export function pickPhotos(
  chosen: File[],
  kept: number,
): { files: File[]; problem: string | null } {
  const files: File[] = [];
  let problem: string | null = null;
  for (const file of chosen) {
    const refused = photoProblem(file);
    if (refused) problem = refused;
    else if (kept + files.length >= MAX_PHOTOS) problem = TOO_MANY_PHOTOS;
    else files.push(file);
  }
  return { files, problem };
}

/** Upload photos one at a time; their upload IDs. A refusal names the photo. */
export async function uploadPhotos(files: File[]): Promise<string[]> {
  const ids: string[] = [];
  for (const file of files) {
    try {
      ids.push((await uploadPhoto(file)).id);
    } catch (error) {
      throw new Error(`${file.name}: ${describeError(error)}`, { cause: error });
    }
  }
  return ids;
}
