<script lang="ts">
  /** The size a shopping list item turns its requests' grams into spools with, and where it
   * came from. Editors and Admins choose another; that re-rounds only the requests' part. */
  import { describeError } from "#lib/api/errors.ts";
  import { setSize, type ShoppingList, type ShoppingListItem } from "#lib/api/shopping.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import { wholeProblem } from "#lib/format.ts";
  import { SIZE, sizeText } from "#lib/shopping-list.ts";

  interface Props {
    item: ShoppingListItem;
    /** The list once the size is chosen. */
    onchanged: (list: ShoppingList) => void;
  }

  let { item, onchanged }: Props = $props();

  let editing = $state(false);
  let grams = $state<number | null>(null);
  let saving = $state(false);
  let failure = $state<string | null>(null);

  const problem = $derived(wholeProblem(grams, SIZE));
  const inputId = $derived(`shopping-size-${item.product.id}`);

  function start(): void {
    grams = item.size.grams;
    failure = null;
    editing = true;
  }

  async function save(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (problem || grams === null) return;
    saving = true;
    failure = null;
    try {
      const list = await setSize(item.product.id, grams);
      editing = false;
      onchanged(list);
    } catch (error) {
      failure = describeError(error);
    } finally {
      saving = false;
    }
  }
</script>

{#if editing}
  <form class="size" aria-label="Choose the size" onsubmit={save}>
    <label for={inputId}>Size in grams</label>
    <input id={inputId} type="number" min="1" max="10000" step="1" bind:value={grams} />
    <button type="submit" class="small primary" disabled={saving || problem !== null}>Save</button>
    <button type="button" class="small" onclick={() => (editing = false)}>Cancel</button>
    {#if problem}<p class="error">{problem}</p>{/if}
    {#if failure}<p role="alert" class="error">{failure}</p>{/if}
  </form>
{:else}
  <p class="size">
    <span>Size: {sizeText(item.size)}</span>
    {#if session.can("editor")}
      <button type="button" class="small" onclick={start}>Change size</button>
    {/if}
  </p>
{/if}

<style>
  .size {
    margin: 0;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px 10px;
    font-size: 14px;
    color: var(--muted);
  }

  .size input {
    width: 7em;
  }

  .size .error {
    flex-basis: 100%;
    margin: 0;
  }
</style>
