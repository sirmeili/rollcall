<script lang="ts">
  /** One catalog color: its swatch ring, name, hex(es) and badges. Pressing it shows its
   * similar in-stock colors underneath. */
  import type { CatalogColor } from "#lib/api/catalog.ts";
  import { hexesText } from "#lib/catalog.ts";
  import HexRing from "#lib/components/catalog/HexRing.svelte";
  import SimilarColors from "#lib/components/catalog/SimilarColors.svelte";

  interface Props {
    color: CatalogColor;
    /** The filament line's material. */
    material: string;
    cutoff: number;
    open: boolean;
    ontoggle: () => void;
  }

  let { color, material, cutoff, open, ontoggle }: Props = $props();

  const detailId = $derived(`similar-${color.uuid}`);
  const similar = $derived(color.similar.length);
</script>

<div class:open>
  <button
    type="button"
    class="crow"
    aria-expanded={open}
    aria-controls={detailId}
    onclick={ontoggle}
  >
    <HexRing hexes={color.hexes} gradient={color.gradient} />
    <span class="cname">{color.name}</span>
    <span class="chex">{hexesText(color.hexes)}</span>
    <span class="badges">
      {#if color.discontinued}<span class="badge-disc">Discontinued</span>{/if}
      {#if color.multi_color}
        <span class="badge-multi">Multi-color</span>
      {:else if similar > 0}
        <span class="badge-sim">{similar} similar in stock</span>
      {:else}
        <span class="nosim">None similar in stock</span>
      {/if}
    </span>
    <svg
      class="chev"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2.4"
      aria-hidden="true"><path d="M6 9l6 6 6-6"></path></svg
    >
  </button>
  {#if open}
    <div id={detailId}><SimilarColors {color} {material} {cutoff} /></div>
  {/if}
</div>

<style>
  .open {
    background: var(--bg);
  }

  .crow {
    width: 100%;
    display: grid;
    grid-template-columns: 30px minmax(150px, 1fr) 190px minmax(0, 1.6fr) 18px;
    align-items: center;
    gap: 14px;
    min-height: 56px;
    padding: 8px 18px;
    border: 0;
    border-radius: 0;
    background: transparent;
    text-align: left;
    font-weight: 400;
  }

  .crow:hover {
    background: var(--chip);
  }

  @media (max-width: 600px) {
    .crow {
      grid-template-columns: 30px minmax(0, 1fr) 18px;
      gap: 4px 12px;
      padding: 10px 16px;
    }

    .crow > :global(:first-child) {
      grid-row: span 3;
    }

    .chex,
    .badges {
      grid-column: 2;
    }

    .chev {
      grid-row: 1 / span 3;
      grid-column: 3;
    }
  }

  .cname {
    font-weight: 600;
    font-size: 15px;
  }

  .chex {
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--muted);
    line-height: 1.35;
  }

  .badges {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
  }

  .chev {
    color: var(--muted);
    transition: transform 0.15s;
  }

  .open .chev {
    transform: rotate(180deg);
  }

  .badge-disc,
  .badge-multi,
  .badge-sim {
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 600;
    white-space: nowrap;
  }

  .badge-disc {
    border: 1px solid var(--muted);
    color: var(--muted);
    padding: 1px 8px;
  }

  .badge-multi {
    background: var(--chip);
    color: var(--text);
  }

  .badge-sim {
    background: var(--okbg);
    color: var(--oktext);
    font-weight: 700;
  }

  .nosim {
    color: var(--muted);
    font-size: 13px;
  }
</style>
