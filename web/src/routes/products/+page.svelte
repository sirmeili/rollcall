<script lang="ts">
  import { describeError } from "#lib/api/errors.ts";
  import { getCatalog } from "#lib/api/catalog.ts";
  import { getInventory, updateProduct } from "#lib/api/stock.ts";
  import type { ProductSummary } from "#lib/api/types.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import { type CatalogEntry, catalogEntries, type LinkPick } from "#lib/catalog-links.ts";
  import CatalogColorDialog from "#lib/components/products/CatalogColorDialog.svelte";
  import ProductTable from "#lib/components/products/ProductTable.svelte";
  import { changesFor, type Draft, draftOf, draftProblem, unsavedText } from "#lib/products.ts";

  let items = $state<ProductSummary[] | null>(null);
  let drafts = $state<Record<number, Draft>>({});
  let failure = $state<string | null>(null);
  let saving = $state(false);
  let message = $state<string | null>(null);

  // The Catalog color dialog: the product it is open for, the cell that opened it, and the
  // catalog, read the first time it opens.
  let openId = $state<number | null>(null);
  let opener: HTMLElement | null = null;
  let entries = $state<CatalogEntry[] | null>(null);
  let storeAddress = $state<string | null>(null);
  let catalogFailure = $state<string | null>(null);
  const byUuid = $derived(new Map((entries ?? []).map((e) => [e.color.uuid, e])));
  const openProduct = $derived(items?.find((item) => item.product.id === openId)?.product);

  const canEdit = $derived(session.can("editor"));
  const changed = $derived(
    (items ?? []).filter((item) => {
      const draft = drafts[item.product.id];
      return draft !== undefined && changesFor(item.product, draft) !== null;
    }),
  );
  const invalid = $derived(Object.values(drafts).some((draft) => draftProblem(draft) !== null));

  function reset(next: ProductSummary[]): void {
    items = next;
    drafts = Object.fromEntries(next.map((item) => [item.product.id, draftOf(item.product)]));
  }

  async function load(): Promise<void> {
    failure = null;
    try {
      reset(await getInventory());
    } catch (error) {
      failure = describeError(error);
    }
  }

  $effect(() => {
    void load();
  });

  async function loadCatalog(): Promise<void> {
    catalogFailure = null;
    try {
      const catalog = await getCatalog();
      entries = catalogEntries(catalog);
      storeAddress = catalog.store_address;
    } catch (error) {
      catalogFailure = `Could not read the catalog. ${describeError(error)}`;
    }
  }

  function openDialog(productId: number, from: HTMLElement): void {
    opener = from;
    openId = productId;
    if (!entries) void loadCatalog();
  }

  function closeDialog(): void {
    openId = null;
    opener?.focus();
  }

  function stage(change: LinkPick): void {
    if (openId !== null) drafts[openId].catalog_color = change;
    closeDialog();
  }

  async function save(): Promise<void> {
    saving = true;
    message = null;
    const problems: string[] = [];
    for (const item of changed) {
      const changes = changesFor(item.product, drafts[item.product.id]);
      if (!changes) continue;
      try {
        await updateProduct(item.product.id, changes);
      } catch (error) {
        problems.push(`${item.product.display_name}: ${describeError(error)}`);
      }
    }
    try {
      const unsaved = problems.length ? { ...drafts } : null;
      reset(await getInventory());
      // Keep what could not be saved, so it can be fixed and saved again.
      if (unsaved) drafts = { ...drafts, ...unsaved };
    } catch (error) {
      problems.push(describeError(error));
    }
    message = problems.length ? `Not saved. ${problems.join(" ")}` : "Saved";
    saving = false;
  }
</script>

<svelte:head><title>Products · RollCall</title></svelte:head>

<div class="page">
  <div class="pagehead">
    <div>
      <h1>Products</h1>
      <p>
        Created automatically from the first tag of each product. Rename them, set when each counts
        as low on stock or nearly out, and check which catalog color each one is.
      </p>
    </div>
    {#if canEdit && items}
      <div class="save">
        {#if message && message !== "Saved"}
          <span role="status" class="error">{message}</span>
        {:else if changed.length}
          <span class="muted">{unsavedText(changed.length)}</span>
        {:else if message}
          <span role="status" class="muted">{message}</span>
        {/if}
        <button
          type="button"
          class="primary"
          disabled={saving || invalid || changed.length === 0}
          onclick={save}>Save changes</button
        >
      </div>
    {/if}
  </div>

  {#if failure}
    <p role="alert" class="error">{failure}</p>
  {:else if !items}
    <p class="muted">Loading…</p>
  {:else if items.length === 0}
    <p class="muted">No products yet. Scan a spool's tag to add its product.</p>
  {:else}
    <ProductTable
      {items}
      drafts={canEdit ? drafts : null}
      entries={byUuid}
      onopen={canEdit ? openDialog : undefined}
    />
    <p class="muted foot">
      Low at: 0 turns the low-stock alert off. Nearly out: an open spool at or below this AMS % is
      marked nearly out. A product added by hand is merged into the real one when one of its tags is
      scanned. Catalog color: products get one from their tag's Bambu code; link the others by hand.
    </p>
  {/if}
</div>

{#if openProduct}
  <CatalogColorDialog
    product={openProduct}
    staged={drafts[openProduct.id]?.catalog_color}
    {entries}
    {storeAddress}
    failure={catalogFailure}
    me={session.user?.username ?? ""}
    onsave={stage}
    onclose={closeDialog}
  />
{/if}

<style>
  .pagehead p {
    max-width: 640px;
  }

  .save {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px;
    font-size: 14px;
  }

  .foot {
    margin: 0;
    font-size: 13px;
  }
</style>
