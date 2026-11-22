<script lang="ts">
  /** A shopping list item in full, on a wide screen: swatch and name, its reasons, Find in
   * store, its recent history, and what to buy in large type. */
  import type { ShoppingList, ShoppingListItem } from "#lib/api/shopping.ts";
  import ItemReasons from "#lib/components/shopping/ItemReasons.svelte";
  import Ring from "#lib/components/ui/Ring.svelte";

  interface Props {
    item: ShoppingListItem;
    storeAddress: string;
    /** Show the product's filament type (items not in the catalog). */
    showType: boolean;
    /** Remove a hand-added reason, by its ID. */
    onremove: (id: number) => void;
    /** The list once the item is changed. */
    onchanged: (list: ShoppingList) => void;
  }

  let { item, storeAddress, showType, onremove, onchanged }: Props = $props();
</script>

<div class="item">
  <Ring rgba={item.product.color_rgba} />
  <div class="body">
    <span class="name">{item.product.display_name}</span>
    {#if showType}
      <span class="type mono">{item.product.filament_type}</span>
    {/if}
    <ItemReasons {item} {storeAddress} {onremove} {onchanged} />
  </div>
  <div class="tobuy">
    <span class="buy">{item.to_buy}</span>
    <span class="label">to buy</span>
  </div>
</div>

<style>
  .item {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: start;
    gap: 16px;
    padding: 16px 18px;
  }

  .body {
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-width: 0;
  }

  .name {
    font-family: var(--font-head);
    font-weight: 600;
    font-size: 17px;
    overflow-wrap: anywhere;
  }

  .type {
    font-size: 13px;
    color: var(--muted);
  }

  .tobuy {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
  }

  .buy {
    font-family: var(--font-head);
    font-size: 40px;
    font-weight: 700;
    line-height: 1;
  }

  .label {
    font-size: 13px;
    color: var(--muted);
  }
</style>
