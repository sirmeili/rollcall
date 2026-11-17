<script lang="ts">
  /** A filament line: a heading that collapses and expands it, and its catalog colors. */
  import { lineCountText, type LineGroup } from "#lib/catalog.ts";
  import CatalogColorRow from "#lib/components/catalog/CatalogColorRow.svelte";

  interface Props {
    group: LineGroup;
    open: boolean;
    ontoggle: () => void;
    /** The ΔE the similar in-stock colors were found with. */
    cutoff: number;
    /** The one catalog color showing its similar colors, if any. */
    expanded: string | null;
    onexpand: (uuid: string) => void;
  }

  let { group, open, ontoggle, cutoff, expanded, onexpand }: Props = $props();

  const headId = $derived(`line-${group.line.uuid}`);
  const rowsId = $derived(`rows-${group.line.uuid}`);
</script>

<section class="group" aria-labelledby={headId}>
  <button
    type="button"
    class="ghead"
    id={headId}
    aria-expanded={open}
    aria-controls={rowsId}
    onclick={ontoggle}
  >
    <svg
      class="gchev"
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2.4"
      aria-hidden="true"><path d="M6 9l6 6 6-6"></path></svg
    >
    <span class="gname">{group.line.name}</span>
    <span class="gmeta">· {group.line.material} · {lineCountText(group)}</span>
  </button>
  {#if open}
    <ul class="rows" id={rowsId}>
      {#each group.colors as color (color.uuid)}
        <li>
          <CatalogColorRow
            {color}
            material={group.line.material}
            {cutoff}
            open={expanded === color.uuid}
            ontoggle={() => onexpand(color.uuid)}
          />
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .group {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 16px;
    overflow: hidden;
  }

  .ghead {
    width: 100%;
    justify-content: flex-start;
    gap: 12px;
    min-height: 60px;
    padding: 0 18px;
    border: 0;
    border-radius: 0;
    background: transparent;
    text-align: left;
  }

  .ghead:hover {
    background: var(--chip);
  }

  .gname {
    font-family: var(--font-head);
    font-size: 19px;
    font-weight: 600;
  }

  .gmeta {
    color: var(--muted);
    font-weight: 500;
    font-size: 14px;
  }

  .gchev {
    color: var(--muted);
    transition: transform 0.15s;
    flex: none;
  }

  .ghead[aria-expanded="false"] .gchev {
    transform: rotate(-90deg);
  }

  .rows {
    margin: 0;
    padding: 0;
    list-style: none;
    border-top: 1px solid var(--line);
  }

  .rows > li + li {
    border-top: 1px solid var(--line);
  }
</style>
