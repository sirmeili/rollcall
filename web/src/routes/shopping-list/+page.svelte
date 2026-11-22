<script lang="ts">
  /** The Shopping list page: each product to buy, as one item with its reasons, grouped by
   * filament line, then Not in the catalog (every role). Editors and Admins add spools by
   * hand and remove them, and choose each item's size. */
  import { describeError } from "#lib/api/errors.ts";
  import { getShoppingList, removeHandReason, type ShoppingList } from "#lib/api/shopping.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import AddToShoppingList from "#lib/components/shopping/AddToShoppingList.svelte";
  import ShoppingGroup from "#lib/components/shopping/ShoppingGroup.svelte";
  import { shoppingGroups } from "#lib/shopping-list.ts";
  import { viewport } from "#lib/viewport.svelte.ts";

  let list = $state<ShoppingList | null>(null);
  let failure = $state<string | null>(null);
  // Why the last change could not be made.
  let changeFailure = $state<string | null>(null);
  let collapsed = $state<Set<string>>(new Set());
  // On a phone, one item at a time is expanded.
  let expanded = $state<number | null>(null);

  const screen = viewport();
  const groups = $derived(list ? shoppingGroups(list) : []);

  async function load(): Promise<void> {
    failure = null;
    try {
      list = await getShoppingList();
    } catch (error) {
      failure = describeError(error);
    }
  }

  async function remove(id: number): Promise<void> {
    changeFailure = null;
    try {
      list = await removeHandReason(id);
    } catch (error) {
      changeFailure = describeError(error);
    }
  }

  function toggle(key: string): void {
    const next = new Set(collapsed);
    if (!next.delete(key)) next.add(key);
    collapsed = next;
  }

  $effect(() => {
    void load();
  });
</script>

<svelte:head><title>Shopping list · RollCall</title></svelte:head>

<div class="page">
  <div class="pagehead">
    <div>
      <h1>Shopping list</h1>
      <p>What to buy, and why.</p>
    </div>
  </div>

  {#if list && session.can("editor")}
    <AddToShoppingList onadded={(next) => (list = next)} />
  {/if}
  {#if changeFailure}<p role="alert" class="error">{changeFailure}</p>{/if}

  {#if failure}
    <p role="alert" class="error">
      {failure} <button class="small" onclick={load}>Try again</button>
    </p>
  {:else if !list}
    <p class="muted">Loading…</p>
  {:else if groups.length === 0}
    <p class="muted">Nothing to buy.</p>
  {:else}
    <div class="groups">
      {#each groups as group (group.key)}
        <ShoppingGroup
          {group}
          storeAddress={list.store_address}
          phone={screen.phone}
          open={!collapsed.has(group.key)}
          ontoggle={() => toggle(group.key)}
          {expanded}
          onexpand={(id) => (expanded = expanded === id ? null : id)}
          onremove={remove}
          onchanged={(next) => (list = next)}
        />
      {/each}
    </div>
  {/if}
</div>

<style>
  .page {
    gap: 20px;
  }

  .groups {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
</style>
