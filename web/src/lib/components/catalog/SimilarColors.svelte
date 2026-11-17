<script lang="ts">
  /** Under an expanded catalog color: its similar in-stock colors, closest first, each
   * with how close it is and how much is on hand. A product of another material says so. */
  import type { CatalogColor } from "#lib/api/catalog.ts";
  import { cutoffText, deltaText, stockText } from "#lib/catalog.ts";
  import HexRing from "#lib/components/catalog/HexRing.svelte";

  interface Props {
    color: CatalogColor;
    /** The filament line's material. */
    material: string;
    cutoff: number;
  }

  let { color, material, cutoff }: Props = $props();
</script>

<div class="detail">
  {#if color.multi_color}
    <p class="muted none">Multi-color: no comparison</p>
  {:else}
    <h4 class="label">Similar in-stock colors</h4>
    {#if color.similar.length === 0}
      <p class="muted none">No similar color in stock</p>
    {:else}
      <ul class="matches">
        {#each color.similar as match (match.product_id)}
          <li class="match">
            <HexRing hexes={[match.hex]} />
            <span class="mtext">
              <a class="mname" href="/spools?q={encodeURIComponent(match.name)}">{match.name}</a>
              {#if match.different_material}
                <span class="warn">⚠ Different material: {match.material}, not {material}</span>
              {/if}
            </span>
            <span class="de">{deltaText(match.delta_e)}</span>
            <span class="stock">{stockText(match.sealed, match.open)}</span>
          </li>
        {/each}
      </ul>
    {/if}
    <p class="foot muted">Showing in-stock products within {cutoffText(cutoff)}</p>
  {/if}
</div>

<style>
  .detail {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 2px 18px 16px 62px;
  }

  @media (max-width: 600px) {
    .detail {
      padding: 2px 16px 16px;
    }
  }

  h4 {
    margin: 4px 0 0;
  }

  .matches {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 2px;
    max-width: 640px;
  }

  .match {
    display: grid;
    grid-template-columns: 30px minmax(0, 1fr) 80px 140px;
    align-items: center;
    gap: 12px;
    min-height: 48px;
  }

  @media (max-width: 600px) {
    .match {
      grid-template-columns: 30px minmax(0, 1fr) auto;
      gap: 4px 12px;
    }

    .stock {
      grid-column: 2 / -1;
    }
  }

  .mtext {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
    min-width: 0;
  }

  .mname {
    font-weight: 600;
    font-size: 14px;
  }

  .mname:hover {
    text-decoration: underline;
  }

  .warn {
    background: var(--lowbg);
    color: var(--lowtext);
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 600;
  }

  .de {
    font-family: var(--font-mono);
    font-size: 13px;
    font-weight: 700;
  }

  .stock {
    font-size: 13px;
    color: var(--muted);
  }

  .none,
  .foot {
    margin: 0;
  }

  .none {
    font-size: 14px;
  }

  .foot {
    font-size: 12px;
  }
</style>
