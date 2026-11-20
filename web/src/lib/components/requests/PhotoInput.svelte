<script lang="ts">
  /** "Add photos": choose one or more JPEG or PNG photos. */
  import { PHOTO_TYPES } from "#lib/requests/photos.ts";

  interface Props {
    disabled?: boolean;
    onpick: (files: File[]) => void;
  }

  let { disabled = false, onpick }: Props = $props();

  function onchange(event: Event): void {
    const target = event.currentTarget as HTMLInputElement;
    const files = [...(target.files ?? [])];
    target.value = "";
    if (files.length) onpick(files);
  }
</script>

<label class="button addph" class:off={disabled}>
  <input
    class="sr-only"
    type="file"
    multiple
    accept={PHOTO_TYPES.join(",")}
    {disabled}
    {onchange}
  />
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2.2"
    aria-hidden="true"
    ><path d="M4 8h3l2-3h6l2 3h3v11H4z"></path><circle cx="12" cy="13" r="3.5"></circle></svg
  >
  Add photos
</label>

<style>
  .addph {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    width: fit-content;
  }

  .addph:focus-within {
    outline: 2px solid var(--accent, currentColor);
    outline-offset: 2px;
  }

  .off {
    opacity: 0.5;
    cursor: default;
  }
</style>
