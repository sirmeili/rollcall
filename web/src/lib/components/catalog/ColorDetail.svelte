<script lang="ts">
  /** What an expanded catalog color shows: its owned products, its linked products with
   * none in stock, its similar in-stock colors, then Find in store and Add to shopping list
   * beside it (a suggestion, for a Viewer). */
  import type { CatalogColor } from "#lib/api/catalog.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import { storeUrl } from "#lib/catalog.ts";
  import AddColorToList from "#lib/components/catalog/AddColorToList.svelte";
  import FindInStore from "#lib/components/catalog/FindInStore.svelte";
  import OwnedProducts from "#lib/components/catalog/OwnedProducts.svelte";
  import SimilarColors from "#lib/components/catalog/SimilarColors.svelte";

  interface Props {
    color: CatalogColor;
    /** The filament line's name and material. */
    lineName: string;
    material: string;
    cutoff: number;
    storeAddress: string;
  }

  let { color, lineName, material, cutoff, storeAddress }: Props = $props();
</script>

<div class="detail">
  <OwnedProducts {color} />
  <SimilarColors {color} {material} {cutoff} />
  <div class="buy">
    <FindInStore href={storeUrl(storeAddress, lineName, color)} />
    {#if session.user}
      <AddColorToList uuid={color.uuid} name={color.name} />
    {/if}
  </div>
</div>

<style>
  .detail {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 2px 18px 16px 62px;
  }

  .buy {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 16px;
  }

  @media (max-width: 600px) {
    .detail {
      padding: 2px 16px 16px;
    }
  }
</style>
