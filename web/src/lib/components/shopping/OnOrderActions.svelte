<script lang="ts">
  /** An item's on order actions (Editors and Admins): Ordered asks how many, starting from
   * to buy, and adds them to on order; Edit on order sets it to any number. */
  import { describeError } from "#lib/api/errors.ts";
  import {
    markOrdered,
    setOnOrder,
    type ShoppingList,
    type ShoppingListItem,
  } from "#lib/api/shopping.ts";
  import { spoolsProblem } from "#lib/shopping-add.ts";
  import { onOrderProblem, orderedDefault } from "#lib/shopping-on-order.ts";

  interface Props {
    item: ShoppingListItem;
    /** The list once the change is made. */
    onchanged: (list: ShoppingList) => void;
  }

  let { item, onchanged }: Props = $props();

  // Which form is open, if any.
  let open = $state<"ordered" | "set" | null>(null);
  let spools = $state<number | null>(null);
  let saving = $state(false);
  let failure = $state<string | null>(null);

  const problem = $derived(
    open === "ordered" ? spoolsProblem(spools) : open === "set" ? onOrderProblem(spools) : null,
  );
  const name = $derived(item.product.display_name);

  function start(which: "ordered" | "set"): void {
    open = which;
    spools = which === "ordered" ? orderedDefault(item) : item.on_order;
    failure = null;
  }

  async function save(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (problem || spools === null) return;
    saving = true;
    failure = null;
    try {
      const id = item.product.id;
      const list =
        open === "ordered" ? await markOrdered(id, spools) : await setOnOrder(id, spools);
      open = null;
      onchanged(list);
    } catch (error) {
      failure = describeError(error);
    } finally {
      saving = false;
    }
  }
</script>

{#if open}
  <form
    class="onorder"
    aria-label={open === "ordered" ? `Ordered ${name}` : `Edit on order ${name}`}
    onsubmit={save}
  >
    <label class="field">
      <span>{open === "ordered" ? "Spools ordered" : "On order"}</span>
      <input
        type="number"
        min={open === "ordered" ? 1 : 0}
        max="999"
        step="1"
        bind:value={spools}
      />
    </label>
    {#if problem}<p class="muted">{problem}</p>{/if}
    {#if failure}<p role="alert" class="error">{failure}</p>{/if}
    <div class="actions">
      <button type="submit" class="primary small" disabled={problem !== null || saving}>Save</button
      >
      <button type="button" class="small" onclick={() => (open = null)}>Cancel</button>
    </div>
  </form>
{:else}
  <div class="actions">
    <button type="button" class="small" onclick={() => start("ordered")}>Ordered</button>
    <button type="button" class="small" onclick={() => start("set")}>Edit on order</button>
  </div>
{/if}

<style>
  .onorder {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-weight: 600;
    font-size: 14px;
  }

  .field input {
    max-width: 120px;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
</style>
