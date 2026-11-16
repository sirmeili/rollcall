<script lang="ts">
  /** One catalog color: its swatch ring, name, hex(es) and badges. */
  import type { CatalogColor } from "#lib/api/catalog.ts";
  import { hexText } from "#lib/catalog.ts";
  import HexRing from "#lib/components/catalog/HexRing.svelte";

  let { color }: { color: CatalogColor } = $props();
</script>

<div class="crow">
  <HexRing hexes={color.hexes} />
  <span class="cname">{color.name}</span>
  <span class="chex">{hexText(color.hexes)}</span>
  <span class="badges">
    {#if color.discontinued}<span class="badge-disc">Discontinued</span>{/if}
    {#if color.multi_color}<span class="badge-multi">Multi-color</span>{/if}
  </span>
</div>

<style>
  .crow {
    display: grid;
    grid-template-columns: 30px minmax(150px, 1fr) 190px minmax(0, 1.6fr);
    align-items: center;
    gap: 14px;
    min-height: 56px;
    padding: 8px 18px;
  }

  @media (max-width: 600px) {
    .crow {
      grid-template-columns: 30px minmax(0, 1fr);
      gap: 4px 12px;
      padding: 10px 16px;
    }

    .crow > :global(:first-child) {
      grid-row: span 3;
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

  .badge-disc {
    border: 1px solid var(--muted);
    color: var(--muted);
    border-radius: 6px;
    padding: 1px 8px;
    font-size: 12px;
    font-weight: 600;
    white-space: nowrap;
  }

  .badge-multi {
    background: var(--chip);
    color: var(--text);
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 600;
    white-space: nowrap;
  }
</style>
