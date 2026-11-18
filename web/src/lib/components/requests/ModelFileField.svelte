<script lang="ts">
  /** The request's model file: drop or choose one, watch it upload, then replace or remove
   * it. The type and size are checked here before uploading; the server checks again. */
  import { describeError } from "#lib/api/errors.ts";
  import { uploadModel, type UploadHandle } from "#lib/api/requests.ts";
  import { fileProblem, type FileState } from "#lib/requests/form.ts";
  import { sizeText } from "#lib/requests/labels.ts";
  import "#lib/requests/requests.css";

  interface Props {
    file: FileState;
    /** The form's problem with the file, once it has been checked. */
    problem: string | null;
  }

  let { file = $bindable(), problem }: Props = $props();

  let input = $state<HTMLInputElement>();
  let over = $state(false);
  let refused = $state<string | null>(null);
  let said = $state("");
  let handle: UploadHandle | null = null;
  let picked: File | null = null;
  // What the field showed before an upload, to go back to if it is cancelled.
  let before: FileState = { status: "none" };

  const shown = $derived(refused ?? problem);

  function choose(): void {
    input?.click();
  }

  function take(chosen: File | undefined): void {
    if (!chosen) return;
    refused = fileProblem(chosen.name, chosen.size);
    if (refused) return;
    if (file.status !== "uploading" && file.status !== "failed") before = file;
    picked = chosen;
    upload(chosen);
  }

  function upload(chosen: File): void {
    const { name, size } = chosen;
    file = { status: "uploading", name, size, percent: 0 };
    said = `Uploading ${name}.`;
    const current = uploadModel(chosen, (percent) => {
      if (handle === current && file.status === "uploading") file = { ...file, percent };
    });
    handle = current;
    current.done.then(
      (done) => {
        if (handle !== current) return;
        handle = null;
        file = { status: "uploaded", upload: done };
        said = `${name} uploaded.`;
      },
      (error) => {
        if (handle !== current) return;
        handle = null;
        const percent = file.status === "uploading" ? file.percent : 0;
        file = { status: "failed", name, size, percent, message: describeError(error) };
        said = `${name} didn't upload.`;
      },
    );
  }

  function cancel(): void {
    const current = handle;
    handle = null;
    current?.cancel();
    file = before;
    said = "Upload cancelled.";
  }

  function retry(): void {
    if (picked) upload(picked);
  }

  function remove(): void {
    file = { status: "none" };
    refused = null;
    said = "File removed.";
  }

  function onpick(event: Event): void {
    const target = event.currentTarget as HTMLInputElement;
    take(target.files?.[0]);
    target.value = "";
  }

  function ondrop(event: DragEvent): void {
    event.preventDefault();
    over = false;
    take(event.dataTransfer?.files[0]);
  }

  const name = $derived(
    file.status === "none" ? "" : file.status === "uploaded" ? file.upload.name : file.name,
  );
  const size = $derived(
    file.status === "none" ? 0 : file.status === "uploaded" ? file.upload.size : file.size,
  );
</script>

<div class="field">
  <span class="flabel" id="req-file-label">File <span class="opt">(optional)</span></span>
  {#if file.status === "none"}
    <div
      class="drop"
      class:over
      class:bad={!!shown}
      role="group"
      aria-labelledby="req-file-label"
      ondragover={(event) => {
        event.preventDefault();
        over = true;
      }}
      ondragleave={() => (over = false)}
      {ondrop}
    >
      <span class="big">Drag a 3MF or STL file here</span>
      <span class="row">
        <span class="muted">or</span>
        <button
          type="button"
          id="req-file"
          aria-describedby="req-file-label req-file-limit"
          onclick={choose}>Choose file</button
        >
      </span>
      <span class="help" id="req-file-limit">One file, up to 95 MB.</span>
    </div>
  {:else}
    <div class="filecard" class:failed={file.status === "failed"}>
      <span class="fi" aria-hidden="true">
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          ><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path><path
            d="M14 3v6h6"
          ></path></svg
        >
      </span>
      <span class="meta">
        <span class="fname">{name}</span>
        {#if file.status === "uploading"}
          <span class="upl">
            <span
              class="pbar"
              role="progressbar"
              aria-label="Uploading {name}"
              aria-valuemin="0"
              aria-valuemax="100"
              aria-valuenow={file.percent}><span style:width="{file.percent}%"></span></span
            >
            <span class="fsize">Uploading… {file.percent}% · {sizeText(size)}</span>
          </span>
        {:else if file.status === "failed"}
          <span class="upfail">Upload failed at {file.percent}%: {file.message}</span>
        {:else}
          <span class="fsize">{sizeText(size)} · uploaded</span>
        {/if}
      </span>
      <span class="acts">
        {#if file.status === "uploading"}
          <button type="button" id="req-file" aria-label="Cancel uploading {name}" onclick={cancel}
            >Cancel upload</button
          >
        {:else if file.status === "failed"}
          <button
            type="button"
            id="req-file"
            aria-label="Try uploading {name} again"
            onclick={retry}>Try again</button
          >
          <button type="button" aria-label="Remove {name}" onclick={remove}>Remove</button>
        {:else}
          <button type="button" id="req-file" aria-label="Replace {name}" onclick={choose}
            >Replace</button
          >
          <button type="button" aria-label="Remove {name}" onclick={remove}>Remove</button>
        {/if}
      </span>
    </div>
  {/if}
  <input
    bind:this={input}
    type="file"
    accept=".3mf,.stl"
    hidden
    aria-label="Model file"
    onchange={onpick}
  />
  {#if shown}<p class="ferr">{shown}</p>{/if}
  <p class="sr-only" role="status">{said}</p>
</div>

<style>
  .drop {
    border: 2px dashed var(--line);
    border-radius: 14px;
    padding: 22px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    text-align: center;
    background: var(--bg);
  }

  .drop.over {
    border-color: var(--accent);
    background: var(--surface);
  }

  .drop.bad {
    border-color: var(--danger);
  }

  .big {
    font-weight: 600;
  }

  .row {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    justify-content: center;
  }

  .upl {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 4px;
  }

  .pbar {
    display: block;
    height: 8px;
    border-radius: 99px;
    background: var(--track);
    overflow: hidden;
  }

  .pbar span {
    display: block;
    height: 100%;
    background: var(--accent);
    border-radius: 99px;
    transition: width 0.2s;
  }

  .upfail {
    font-size: 13px;
    font-weight: 600;
    color: var(--danger);
  }
</style>
