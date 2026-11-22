<script lang="ts">
  /** A shopping list item on a phone (docs/mockups/mobile-web/PhoneShoppingList.html): a
   * compact row that expands in place to its reasons, Find in store and recent history, as on
   * Spools. */
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
    open: boolean;
    ontoggle: () => void;
  }

  let { item, storeAddress, showType, onremove, onchanged, open, ontoggle }: Props = $props();

  const detailId = $derived(`shopping-detail-${item.product.id}`);
</script>

<button
  type="button"
  class="crow"
  class:open
  aria-expanded={open}
  aria-controls={detailId}
  onclick={ontoggle}
>
  <Ring rgba={item.product.color_rgba} size="sm" />
  <span class="text">
    <span class="name">{item.product.display_name}</span>
    {#if showType}
      <span class="type mono">{item.product.filament_type}</span>
    {/if}
  </span>
  <span class="tobuy"><span class="buy">{item.to_buy}</span> <span class="label">to buy</span></span
  >
  <svg
    class="chev"
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2.4"
    aria-hidden="true"
  >
    <path d="M6 9l6 6 6-6"></path>
  </svg>
</button>
{#if open}
  <div class="detail" id={detailId}>
    <ItemReasons {item} {storeAddress} {onremove} {onchanged} />
  </div>
{/if}

<style>
  .crow {
    width: 100%;
    display: grid;
    grid-template-columns: 30px minmax(0, 1fr) auto 16px;
    align-items: center;
    justify-content: stretch;
    gap: 10px;
    min-height: 60px;
    padding: 10px 12px 10px 14px;
    border: 0;
    border-radius: 0;
    background: transparent;
    text-align: left;
    font-weight: 400;
  }

  .text {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .name {
    font-family: var(--font-head);
    font-weight: 600;
    font-size: 15px;
    line-height: 1.25;
    overflow-wrap: anywhere;
  }

  .type {
    font-size: 12px;
    color: var(--muted);
  }

  .tobuy {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
  }

  .buy {
    font-family: var(--font-head);
    font-size: 24px;
    font-weight: 700;
    line-height: 1;
  }

  .label {
    font-size: 11px;
    color: var(--muted);
  }

  .chev {
    color: var(--muted);
    transition: transform 0.15s;
  }

  .crow.open .chev {
    transform: rotate(180deg);
  }

  .detail {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 0 14px 14px 54px;
  }
</style>
