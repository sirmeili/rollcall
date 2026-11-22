<script lang="ts">
  /** The Shopping list page: each product to buy, as one item with its reasons, grouped by
   * filament line, then Not in the catalog (every role), with Viewers' suggestions at the top
   * and a Dismissed filter. Editors and Admins add spools by hand and remove them, mark items
   * Ordered and set what is on order, choose each item's size, dismiss items and bring them
   * back, and add or dismiss suggestions; Viewers suggest. A link to one item (from a
   * request's short choice) names it in the address, #shopping-item-<product ID>: the page
   * scrolls to it, expanded on a phone. */
  import { tick } from "svelte";
  import { describeError } from "#lib/api/errors.ts";
  import {
    addSuggestion,
    bringBack,
    dismissItem,
    dismissSuggestion,
    getShoppingList,
    removeHandReason,
    type ShoppingList,
  } from "#lib/api/shopping.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import AddToShoppingList from "#lib/components/shopping/AddToShoppingList.svelte";
  import DismissedItems from "#lib/components/shopping/DismissedItems.svelte";
  import ShoppingGroup from "#lib/components/shopping/ShoppingGroup.svelte";
  import SuggestionsSection from "#lib/components/shopping/SuggestionsSection.svelte";
  import { shoppingBadge } from "#lib/shopping-badge.svelte.ts";
  import { shoppingGroups } from "#lib/shopping-list.ts";
  import { viewport } from "#lib/viewport.svelte.ts";

  let list = $state<ShoppingList | null>(null);
  let failure = $state<string | null>(null);
  // Why the last change could not be made.
  let changeFailure = $state<string | null>(null);
  let collapsed = $state<Set<string>>(new Set());
  // On a phone, one item at a time is expanded.
  let expanded = $state<number | null>(null);
  // A suggestion is being added or dismissed.
  let deciding = $state(false);
  // The Dismissed filter: the dismissed items instead of the list.
  let showDismissed = $state(false);

  const screen = viewport();
  const groups = $derived(list ? shoppingGroups(list) : []);

  async function load(): Promise<void> {
    failure = null;
    try {
      list = await getShoppingList();
    } catch (error) {
      failure = describeError(error);
      return;
    }
    await showLinked();
  }

  /** Scroll to the item the address names, if any, expanding it on a phone. */
  async function showLinked(): Promise<void> {
    const named = /^#shopping-item-(\d+)$/.exec(window.location.hash);
    if (!named) return;
    expanded = Number(named[1]);
    await tick();
    document.getElementById(`shopping-item-${named[1]}`)?.scrollIntoView();
  }

  async function change(made: Promise<ShoppingList>): Promise<void> {
    changeFailure = null;
    try {
      list = await made;
    } catch (error) {
      changeFailure = describeError(error);
    }
  }

  const remove = (id: number) => change(removeHandReason(id));
  const dismiss = (productId: number) => change(dismissItem(productId));
  const restore = (productId: number) => change(bringBack(productId));

  async function decide(change: (id: number) => Promise<ShoppingList>, id: number): Promise<void> {
    changeFailure = null;
    deciding = true;
    try {
      list = await change(id);
    } catch (error) {
      changeFailure = describeError(error);
    } finally {
      deciding = false;
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

  // The Shopping list link's count follows the open suggestions shown.
  $effect(() => {
    if (list) shoppingBadge.count = list.suggestions.length;
  });
</script>

<svelte:head><title>Shopping list · RollCall</title></svelte:head>

<div class="page">
  <div class="pagehead">
    <div>
      <h1>Shopping list</h1>
      <p>What to buy, and why.</p>
    </div>
    {#if list}
      <button
        type="button"
        class="chip"
        aria-pressed={showDismissed}
        onclick={() => (showDismissed = !showDismissed)}>Dismissed ({list.dismissed.length})</button
      >
    {/if}
  </div>

  {#if list && session.user}
    <AddToShoppingList onadded={(next) => (list = next)} />
  {/if}
  {#if changeFailure}<p role="alert" class="error">{changeFailure}</p>{/if}

  {#if failure}
    <p role="alert" class="error">
      {failure} <button class="small" onclick={load}>Try again</button>
    </p>
  {:else if !list}
    <p class="muted">Loading…</p>
  {:else}
    {#if list.suggestions.length > 0}
      <SuggestionsSection
        suggestions={list.suggestions}
        busy={deciding}
        onadd={(id) => decide(addSuggestion, id)}
        ondismiss={(id) => decide(dismissSuggestion, id)}
      />
    {/if}
    {#if showDismissed}
      <DismissedItems items={list.dismissed} onbringback={restore} />
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
            ondismiss={dismiss}
            onchanged={(next) => (list = next)}
          />
        {/each}
      </div>
    {/if}
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
