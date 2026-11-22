<script lang="ts">
  /** A filament line of the shopping list, or Not in the catalog: its heading with the
   * group's to buy, and its items. On a phone the heading collapses and expands the group,
   * as on the phone Catalog page, and each item is a compact row. Items fully ordered come
   * last, under an On order label. */
  import type { ShoppingList, ShoppingListItem } from "#lib/api/shopping.ts";
  import ShoppingItem from "#lib/components/shopping/ShoppingItem.svelte";
  import ShoppingItemRow from "#lib/components/shopping/ShoppingItemRow.svelte";
  import type { ShoppingGroup } from "#lib/shopping-list.ts";
  import { byOrdered } from "#lib/shopping-on-order.ts";

  interface Props {
    group: ShoppingGroup;
    storeAddress: string;
    phone: boolean;
    /** On a phone: whether the group is expanded. */
    open: boolean;
    ontoggle: () => void;
    /** On a phone: the one product expanded, if any. */
    expanded: number | null;
    onexpand: (productId: number) => void;
    /** Remove a hand-added reason, by its ID. */
    onremove: (id: number) => void;
    /** The list once an item is changed. */
    onchanged: (list: ShoppingList) => void;
    /** Dismiss an item, by its product's ID. */
    ondismiss: (productId: number) => void;
  }

  let {
    group,
    storeAddress,
    phone,
    open,
    ontoggle,
    expanded,
    onexpand,
    onremove,
    onchanged,
    ondismiss,
  }: Props = $props();

  const label = $derived(`${group.name}, ${group.toBuy} to buy`);
  const rowsId = $derived(`shopping-rows-${group.key}`);
  const split = $derived(byOrdered(group.items));
</script>

{#snippet rows(items: ShoppingListItem[], label?: string)}
  <ul class="rows" aria-label={label}>
    {#each items as item (item.product.id)}
      <li id={`shopping-item-${item.product.id}`}>
        {#if phone}
          <ShoppingItemRow
            {item}
            {storeAddress}
            showType={group.showType}
            {onremove}
            {onchanged}
            {ondismiss}
            open={expanded === item.product.id}
            ontoggle={() => onexpand(item.product.id)}
          />
        {:else}
          <ShoppingItem
            {item}
            {storeAddress}
            showType={group.showType}
            {onremove}
            {onchanged}
            {ondismiss}
          />
        {/if}
      </li>
    {/each}
  </ul>
{/snippet}

<section class="group" aria-label={label}>
  {#if phone}
    <button
      type="button"
      class="ghead"
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
      <span class="gname">{group.name}</span>
      <span class="gmeta">· {group.toBuy} to buy</span>
    </button>
  {:else}
    <h2 class="ghead">
      <span class="gname">{group.name}</span>
      <span class="gmeta">· {group.toBuy} to buy</span>
    </h2>
  {/if}
  {#if !phone || open}
    <div id={rowsId}>
      {#if split.toBuy.length > 0}
        {@render rows(split.toBuy)}
      {/if}
      {#if split.ordered.length > 0}
        <h3 class="sub">On order</h3>
        {@render rows(split.ordered, "On order")}
      {/if}
    </div>
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
    display: flex;
    align-items: center;
    justify-content: flex-start;
    flex-wrap: wrap;
    gap: 8px 12px;
    min-height: 56px;
    margin: 0;
    padding: 0 18px;
    border: 0;
    border-radius: 0;
    background: transparent;
    text-align: left;
    font-size: inherit;
  }

  button.ghead:hover {
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

  .sub {
    margin: 0;
    padding: 10px 18px 6px;
    border-top: 1px solid var(--line);
    font-size: 13px;
    font-weight: 600;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .sub + .rows {
    border-top: 0;
  }

  .rows > li + li {
    border-top: 1px solid var(--line);
  }
</style>
