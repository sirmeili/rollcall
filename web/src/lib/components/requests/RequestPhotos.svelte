<script lang="ts">
  /** Photos of the finished print, as the model file section shows its file: thumbnails
   * that open full size. A signed-in Admin adds and removes them while the request is Done
   * or Picked Up. */
  import { describeError } from "#lib/api/errors.ts";
  import { addPhotos, type PrintRequest, photoUrl, removePhoto } from "#lib/api/requests.ts";
  import PhotoInput from "#lib/components/requests/PhotoInput.svelte";
  import { MAX_PHOTOS, pickPhotos, uploadPhotos } from "#lib/requests/photos.ts";
  import "#lib/requests/requests.css";

  interface Props {
    request: PrintRequest;
    /** The request as it is after a change. */
    onchange: (request: PrintRequest) => void;
  }

  let { request, onchange }: Props = $props();

  let busy = $state(false);
  let problem = $state<string | null>(null);

  async function add(chosen: File[]): Promise<void> {
    const picked = pickPhotos(chosen, request.photos.length);
    problem = picked.problem;
    if (!picked.files.length) return;
    busy = true;
    try {
      const ids = await uploadPhotos(picked.files);
      onchange(await addPhotos(request.id, ids));
    } catch (error) {
      problem = error instanceof Error ? error.message : describeError(error);
    } finally {
      busy = false;
    }
  }

  async function remove(photoId: string): Promise<void> {
    busy = true;
    problem = null;
    try {
      onchange(await removePhoto(request.id, photoId));
    } catch (error) {
      problem = describeError(error);
    } finally {
      busy = false;
    }
  }
</script>

<section class="card sect" aria-labelledby="h-photos">
  <h2 id="h-photos">Photos</h2>
  {#if request.photos.length}
    <ul class="photos">
      {#each request.photos as photo (photo.id)}
        {@const url = photoUrl(request.id, photo.id)}
        <li>
          <a href={url} target="_blank" rel="noopener" title="Open {photo.name} full size">
            <img src={url} alt={photo.name} loading="lazy" />
          </a>
          {#if request.can_change_photos}
            <button
              type="button"
              disabled={busy}
              aria-label="Remove {photo.name}"
              onclick={() => remove(photo.id)}>Remove</button
            >
          {/if}
        </li>
      {/each}
    </ul>
  {:else}
    <p class="muted nophotos">No photos yet.</p>
  {/if}
  {#if request.can_change_photos && request.photos.length < MAX_PHOTOS}
    <PhotoInput disabled={busy} onpick={add} />
    <span class="help">Up to {MAX_PHOTOS} JPEG or PNG photos, 20 MB each.</span>
  {/if}
  {#if problem}<p role="alert" class="error">{problem}</p>{/if}
</section>

<style>
  .photos {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 12px;
  }

  li {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  a {
    display: block;
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid var(--line);
    background: var(--chip);
    aspect-ratio: 1;
  }

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .nophotos,
  .error {
    margin: 0;
  }

  .help {
    font-size: 13px;
    color: var(--muted);
  }
</style>
