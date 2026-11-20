<script lang="ts">
  /** A request's filament choices in order, with the stock and catalog as they are now. A
   * catalog color shows the similar colors in stock and Find in store; a multi-color one
   * gets no comparison, and one the catalog has dropped says so. Once approved, each shows
   * its grams and holds (ChoiceHolds). */
  import type { Choice } from "#lib/api/requests.ts";
  import { stockText, storeSearchUrl } from "#lib/catalog.ts";
  import FindInStore from "#lib/components/catalog/FindInStore.svelte";
  import ChoiceHolds from "#lib/components/requests/ChoiceHolds.svelte";
  import HexRing from "#lib/components/catalog/HexRing.svelte";
  import { similarText } from "#lib/requests/labels.ts";
  import "#lib/requests/requests.css";

  interface Props {
    choices: Choice[];
    /** The store Find in store searches. */
    storeAddress: string;
  }

  let { choices, storeAddress }: Props = $props();

  function productSub(choice: Choice): string {
    const stock = stockText(choice.sealed ?? 0, choice.open ?? 0) || "none left";
    return [choice.material, stock].filter(Boolean).join(" · ");
  }

  function colorSub(choice: Choice): string {
    const code = choice.bambu_code ? ` · ${choice.bambu_code}` : "";
    return `${choice.material}${code} · not in stock`;
  }

  function storeHref(choice: Choice): string {
    return storeSearchUrl(
      storeAddress,
      choice.line ?? "",
      choice.color_name ?? choice.name,
      choice.bambu_code,
    );
  }
</script>

<ol class="choices" aria-label="Filament choices, in order">
  {#each choices as choice, i (i)}
    <li class="choice">
      <span class="ord" aria-hidden="true">{i + 1}</span>
      <HexRing hexes={choice.hexes} />
      <span class="cinfo">
        <span class="cname"><span class="sr-only">Choice {i + 1}:</span> {choice.name}</span>
        {#if choice.kind === "product"}
          <span class="csub"><span class="kind own">Owned</span> {productSub(choice)}</span>
        {:else if !choice.in_catalog}
          <span class="csub"><span class="kind cat">Catalog</span> No longer in the catalog</span>
        {:else}
          <span class="csub"
            ><span class="kind cat">Catalog</span>
            {colorSub(choice)}<br />{similarText(
              choice.multi_color ? null : choice.similar.map((match) => match.name),
            )}</span
          >
        {/if}
        <ChoiceHolds {choice} />
      </span>
      <span class="end">
        {#if choice.note}
          <span class="cnote">“{choice.note}”</span>
        {:else}
          <span class="cnote none">No note</span>
        {/if}
        {#if choice.kind === "catalog_color" && choice.in_catalog}
          <FindInStore href={storeHref(choice)} />
        {/if}
      </span>
    </li>
  {/each}
</ol>

<style>
  .end {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 8px;
  }

  .cnote {
    font-size: 14px;
    font-style: italic;
    text-align: right;
    max-width: 200px;
  }

  .cnote.none {
    color: var(--muted);
    font-style: normal;
    font-size: 13px;
  }

  @media (max-width: 600px) {
    .end {
      align-items: flex-start;
    }

    .cnote {
      text-align: left;
      max-width: none;
    }
  }
</style>
