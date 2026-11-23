<script lang="ts">
  /** A form whose Save waits for `before` (a check, a picked file) before it writes, as a
   * new form might. */
  import { api } from "#lib/api/client.ts";

  let { before }: { before: () => Promise<void> } = $props();

  let name = $state("");
  let saved = $state(false);

  async function save(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    await before();
    await api("/things/1", { method: "PUT", body: { name } });
    saved = true;
  }
</script>

<form onsubmit={save}>
  <label>Name<input type="text" bind:value={name} /></label>
  <button type="submit">Save</button>
  {#if saved}<p role="status">Saved</p>{/if}
</form>
