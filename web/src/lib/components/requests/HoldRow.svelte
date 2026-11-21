<script lang="ts">
  /** One hold in the holds editor: its spool and grams to save in its place, or Remove. */
  import { untrack } from "svelte";
  import type { Hold } from "#lib/api/requests.ts";
  import type { SpoolRow } from "#lib/api/types.ts";
  import { GRAMS_MAX, spoolText } from "#lib/requests/labels.ts";

  interface Props {
    hold: Hold;
    /** The spools on the shelf. */
    spools: SpoolRow[];
    busy: boolean;
    onsave: (spoolId: number, grams: number) => void;
    onremove: () => void;
  }

  let { hold, spools, busy, onsave, onremove }: Props = $props();

  let spool = $state(untrack(() => hold.spool_id));
  let grams = $state<number | null>(untrack(() => hold.grams));
  const label = $derived(`Hold on spool #${hold.spool_id}`);
  // The spools to choose from, with the held one first when it isn't listed.
  const options = $derived([
    ...(spools.some((found) => found.id === hold.spool_id)
      ? []
      : [{ id: hold.spool_id, text: `#${hold.spool_id} ${hold.product_name}` }]),
    ...spools.map((found) => ({ id: found.id, text: spoolText(found) })),
  ]);
</script>

<fieldset class="row" aria-label={label}>
  <span class="line">
    <select aria-label="Spool" bind:value={spool}>
      {#each options as option (option.id)}
        <option value={option.id}>{option.text}</option>
      {/each}
    </select>
    <input type="number" min="1" max={GRAMS_MAX} step="1" aria-label="Grams" bind:value={grams} />
  </span>
  <span class="line">
    <button type="button" disabled={busy} onclick={() => onsave(spool, Number(grams))}>Save</button>
    <button type="button" disabled={busy} onclick={onremove}>Remove</button>
  </span>
</fieldset>

<style>
  .row {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin: 0;
    padding: 0;
    border: 0;
  }

  .line {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }

  select {
    flex: 1 1 200px;
    min-width: 0;
  }

  input {
    width: 110px;
  }
</style>
