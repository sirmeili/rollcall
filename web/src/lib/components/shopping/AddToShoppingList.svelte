<script lang="ts">
  /** Add to shopping list on the list page: search every product and the catalog colors no
   * product is linked to, pick one, and add a number of spools. Editors and Admins add them
   * by hand, a catalog color getting its "From the catalog" product on the server; Viewers
   * make a suggestion. */
  import { listProducts } from "#lib/api/admin.ts";
  import { getCatalog, type Catalog } from "#lib/api/catalog.ts";
  import { describeError } from "#lib/api/errors.ts";
  import { addByHand, suggest, type ShoppingList } from "#lib/api/shopping.ts";
  import type { Product } from "#lib/api/types.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import HexRing from "#lib/components/catalog/HexRing.svelte";
  import { wholeProblem } from "#lib/format.ts";
  import { type AddOption, addOptions, SPOOLS, searchAdd } from "#lib/shopping-add.ts";

  interface Props {
    /** The list once the spools are added or suggested. */
    onadded: (list: ShoppingList) => void;
  }

  let { onadded }: Props = $props();

  let open = $state(false);
  let options = $state<AddOption[]>([]);
  let loadFailure = $state<string | null>(null);
  let query = $state("");
  let picked = $state<string | null>(null);
  let spools = $state<number | null>(1);
  let saving = $state(false);
  let failure = $state<string | null>(null);

  const found = $derived(searchAdd(options, query));
  const choice = $derived(options.find((o) => o.key === picked));
  const problem = $derived(wholeProblem(spools, SPOOLS));
  const editor = $derived(session.can("editor"));

  async function start(): Promise<void> {
    open = true;
    query = "";
    picked = null;
    spools = 1;
    failure = null;
    const [products, catalog] = await Promise.allSettled([listProducts(), getCatalog()]);
    const failed = [products, catalog].find((r) => r.status === "rejected");
    loadFailure = failed
      ? `Some filament couldn't be loaded: ${describeError(failed.reason)}`
      : null;
    options = addOptions(
      products.status === "fulfilled" ? (products.value as Product[]) : [],
      catalog.status === "fulfilled" ? (catalog.value as Catalog) : null,
    );
  }

  async function add(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (!choice || problem || spools === null) return;
    saving = true;
    failure = null;
    try {
      const list = await (editor ? addByHand : suggest)(choice.target, spools);
      open = false;
      onadded(list);
    } catch (error) {
      failure = describeError(error);
    } finally {
      saving = false;
    }
  }
</script>

{#if !open}
  <button type="button" class="primary" onclick={start}>Add to shopping list</button>
{:else}
  <form class="add" aria-label="Add to shopping list" onsubmit={add}>
    {#if loadFailure}<p role="alert" class="error">{loadFailure}</p>{/if}
    <label class="field">
      <span>Product or catalog color</span>
      <!-- svelte-ignore a11y_autofocus -->
      <input type="search" bind:value={query} autocomplete="off" autofocus />
    </label>
    {#if query.trim() && found.length === 0}
      <p class="muted">Nothing matches "{query.trim()}".</p>
    {:else if found.length > 0}
      <div class="options">
        {#each found as option (option.key)}
          <label class="option">
            <input type="radio" name="add-pick" value={option.key} bind:group={picked} />
            <HexRing hexes={option.hexes} />
            <span class="otext">
              <span class="oname">{option.name}</span>
              <span class="osub">{option.sub}</span>
            </span>
          </label>
        {/each}
      </div>
    {/if}
    <label class="field spools">
      <span>Spools</span>
      <input type="number" min="1" max="999" step="1" bind:value={spools} />
    </label>
    {#if failure}<p role="alert" class="error">{failure}</p>{/if}
    <div class="actions">
      <button type="submit" class="primary" disabled={!choice || problem !== null || saving}
        >{editor ? "Add" : "Suggest"}</button
      >
      <button type="button" onclick={() => (open = false)}>Cancel</button>
    </div>
  </form>
{/if}

<style>
  .add {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 16px 18px;
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 16px;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-weight: 600;
  }

  .spools input {
    max-width: 120px;
  }

  .options {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .option {
    display: grid;
    grid-template-columns: auto auto minmax(0, 1fr);
    align-items: center;
    gap: 10px;
    padding: 6px 8px;
    border-radius: 10px;
  }

  .option:hover {
    background: var(--chip);
  }

  .otext {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .oname {
    font-weight: 600;
    overflow-wrap: anywhere;
  }

  .osub {
    font-size: 13px;
    color: var(--muted);
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
</style>
