<script lang="ts">
  /** The Catalog color dialog's search: catalog colors by name, line or Bambu code, each
   * with its swatch, name, line and Bambu code. Pressing one picks it. */
  import { type CatalogEntry, entryLabel, searchEntries } from "#lib/catalog-links.ts";
  import Ring from "#lib/components/ui/Ring.svelte";

  interface Props {
    entries: CatalogEntry[];
    /** The product's material, listed before anything is typed. */
    material: string;
    /** The UUID of the color picked or linked, shown pressed. */
    selected: string | null;
    onpick: (uuid: string) => void;
  }

  let { entries, material, selected, onpick }: Props = $props();

  let query = $state("");
  const result = $derived(searchEntries(entries, query, material));
</script>

<label class="label" for="cc-q">Link to a catalog color</label>
<input
  id="cc-q"
  type="search"
  placeholder="Search color, line or Bambu code"
  autocomplete="off"
  bind:value={query}
/>
<p class="count" role="status">{result.text}</p>
{#if result.shown.length}
  <ul class="results" aria-label="Catalog colors">
    {#each result.shown as entry (entry.color.uuid)}
      <li>
        <button
          type="button"
          class="res"
          aria-pressed={entry.color.uuid === selected}
          aria-label={entryLabel(entry)}
          onclick={() => onpick(entry.color.uuid)}
        >
          <Ring rgba="{entry.color.hexes[0]}FF" size="sm" />
          <span><span class="n">{entry.color.name}</span><span class="l">{entry.line}</span></span>
          {#if entry.color.bambu_code}
            <span class="c">{entry.color.bambu_code}</span>
          {:else}
            <span class="c none">No Bambu code</span>
          {/if}
        </button>
      </li>
    {/each}
  </ul>
{/if}

<style>
  .label {
    margin: 0;
  }

  input {
    width: 100%;
    box-sizing: border-box;
  }

  .count {
    font-size: 13px;
    color: var(--muted);
    margin: 0;
  }

  .results {
    list-style: none;
    margin: 0;
    padding: 0;
    border: 1px solid var(--line);
    border-radius: 12px;
    overflow: hidden;
  }

  .results li + li {
    border-top: 1px solid var(--line);
  }

  .res {
    border: 0;
    border-radius: 0;
    width: 100%;
    min-height: 52px;
    padding: 8px 14px;
    display: grid;
    grid-template-columns: 22px 1fr auto;
    gap: 12px;
    align-items: center;
    justify-items: start;
    text-align: left;
    font-weight: 400;
    background: transparent;
  }

  .res:hover {
    background: var(--bg);
  }

  .res[aria-pressed="true"] {
    background: var(--chip);
    box-shadow: inset 3px 0 0 var(--accent);
  }

  .n {
    font-weight: 600;
    display: block;
  }

  .l {
    font-size: 13px;
    color: var(--muted);
  }

  .c {
    font-family: var(--font-mono);
    font-size: 13px;
    justify-self: end;
  }

  .c.none {
    color: var(--muted);
    font-family: var(--font-body);
    font-size: 12px;
  }
</style>
