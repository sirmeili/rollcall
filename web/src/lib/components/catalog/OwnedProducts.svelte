<script lang="ts">
  /** Under an expanded catalog color: the in-stock products linked to it, each with how it
   * was linked and its counts, then a quiet line for each linked product with none in
   * stock. Kept apart from the similar in-stock colors, which are substitutes. */
  import type { CatalogColor } from "#lib/api/catalog.ts";
  import { howText, stockText } from "#lib/catalog.ts";
  import HexRing from "#lib/components/catalog/HexRing.svelte";

  interface Props {
    color: CatalogColor;
  }

  let { color }: Props = $props();

  function spools(name: string): string {
    return `/spools?q=${encodeURIComponent(name)}`;
  }
</script>

{#if color.owned_products.length}
  <h4 class="label">Owned</h4>
  <ul class="matches">
    {#each color.owned_products as product (product.product_id)}
      <li class="match">
        <HexRing hexes={[product.hex]} />
        <span class="mtext">
          <a class="mname" href={spools(product.name)}>{product.name}</a>
          <span class="how muted">{howText(product.how)}</span>
        </span>
        <span class="stock">{stockText(product.sealed, product.open)}</span>
      </li>
    {/each}
  </ul>
{/if}
{#each color.linked_none_in_stock as product (product.product_id)}
  <p class="muted linked-none">
    Linked: <a href={spools(product.name)}>{product.name}</a>, none in stock
  </p>
{/each}

<style>
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
    grid-template-columns: 30px minmax(0, 1fr) 140px;
    align-items: center;
    gap: 12px;
    min-height: 48px;
  }

  .mtext {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    min-width: 0;
  }

  .mname {
    font-weight: 600;
    font-size: 14px;
  }

  .mname:hover {
    text-decoration: underline;
  }

  .how {
    font-size: 12px;
  }

  .stock {
    font-size: 13px;
    color: var(--muted);
  }

  .linked-none {
    margin: 0;
    font-size: 14px;
  }

  .linked-none a {
    text-decoration: underline;
  }
</style>
