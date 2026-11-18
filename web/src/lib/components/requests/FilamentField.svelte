<script lang="ts">
  /** The request's filament: the choices in order, each with a note, and a search to add
   * in-stock products or catalog colors no one has in stock. */
  import HexRing from "#lib/components/catalog/HexRing.svelte";
  import { NOTE_MAX } from "#lib/requests/form.ts";
  import {
    chosenSub,
    searchOptions,
    type Chosen,
    type FilamentOption,
    type PickerOptions,
  } from "#lib/requests/picker.ts";
  import "#lib/requests/requests.css";

  interface Props {
    choices: Chosen[];
    options: PickerOptions;
    /** The form's problem with the choices, once it has been checked. */
    problem: string | null;
    /** Why the picker has nothing to offer (it failed to load). */
    failure?: string | null;
  }

  let { choices = $bindable(), options, problem, failure = null }: Props = $props();

  let query = $state("");
  let said = $state("");
  const found = $derived(searchOptions(options, query));
  const chosenKeys = $derived(new Set(choices.map((choice) => choice.key)));

  function add(option: FilamentOption): void {
    choices = [...choices, { ...option, note: "" }];
    said = `Added ${option.name}.`;
  }

  function move(from: number, to: number): void {
    const next = [...choices];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    choices = next;
    said = `${moved.name} is now choice ${to + 1}.`;
  }

  function remove(at: number): void {
    said = `Removed ${choices[at].name}.`;
    choices = choices.filter((_, i) => i !== at);
  }
</script>

{#snippet icon(path: string)}
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2.4"
    aria-hidden="true"><path d={path}></path></svg
  >
{/snippet}

{#snippet result(option: FilamentOption)}
  {@const added = chosenKeys.has(option.key)}
  <li>
    <button
      type="button"
      class="res"
      disabled={added}
      aria-label="{added ? 'Added' : 'Add'} {option.name}"
      onclick={() => add(option)}
    >
      <HexRing hexes={option.hexes} />
      <span class="cinfo">
        <span class="cname">{option.name}</span>
        <span class="csub">{chosenSub(option, 2)}</span>
      </span>
      <span class="add">
        {#if added}Added{:else}{@render icon("M12 5v14M5 12h14")}Add{/if}
      </span>
    </button>
  </li>
{/snippet}

<ol class="choices" aria-label="Filament choices, in order">
  {#each choices as choice, i (choice.key)}
    <li class="choice editable">
      <span class="ord" aria-hidden="true">{i + 1}</span>
      <HexRing hexes={choice.hexes} />
      <span class="cinfo">
        <span class="cname"><span class="sr-only">Choice {i + 1}:</span> {choice.name}</span>
        <span class="csub"
          ><span class="kind {choice.kind === 'product' ? 'own' : 'cat'}"
            >{choice.kind === "product" ? "Owned" : "Catalog"}</span
          >
          {chosenSub(choice)}</span
        >
      </span>
      <input
        type="text"
        maxlength={NOTE_MAX}
        placeholder="Note, like main body"
        aria-label="Note for {choice.name}"
        bind:value={choices[i].note}
      />
      <span class="cacts">
        <button
          type="button"
          aria-label="Move {choice.name} up"
          disabled={i === 0}
          onclick={() => move(i, i - 1)}>{@render icon("M12 19V5M5 12l7-7 7 7")}</button
        >
        <button
          type="button"
          aria-label="Move {choice.name} down"
          disabled={i === choices.length - 1}
          onclick={() => move(i, i + 1)}>{@render icon("M12 5v14M5 12l7 7 7-7")}</button
        >
        <button type="button" aria-label="Remove {choice.name}" onclick={() => remove(i)}
          >{@render icon("M6 6l12 12M18 6 6 18")}</button
        >
      </span>
    </li>
  {:else}
    <li class="nochoice" class:bad={!!problem}>No filament yet. Search below to add one.</li>
  {/each}
</ol>
{#if problem}<p class="ferr">{problem}</p>{/if}

<div class="picker">
  <label class="flabel" for="req-filament">Add filament</label>
  <input
    id="req-filament"
    type="search"
    placeholder="Search your products and catalog colors"
    autocomplete="off"
    aria-describedby="req-filament-count"
    bind:value={query}
  />
  {#if failure}
    <p class="ferr">{failure}</p>
  {:else}
    <p class="rcount" id="req-filament-count" role="status">{found.summary}</p>
  {/if}
  {#if found.products.length || found.colors.length}
    <div class="results">
      {#if found.products.length}
        <p class="rgroup">Your products · in stock</p>
        <ul class="rlist">
          {#each found.products as option (option.key)}{@render result(option)}{/each}
        </ul>
      {/if}
      {#if found.colors.length}
        <p class="rgroup">Catalog colors · not in stock</p>
        <ul class="rlist">
          {#each found.colors as option (option.key)}{@render result(option)}{/each}
        </ul>
      {/if}
    </div>
  {/if}
  <p class="sr-only" role="status">{said}</p>
</div>

<style>
  .choice.editable {
    grid-template-columns: 28px 30px minmax(0, 1fr) 220px auto;
  }

  .choice input {
    min-height: 40px;
    font-size: 14px;
  }

  .cacts {
    display: flex;
    gap: 4px;
  }

  .cacts button {
    width: 40px;
    min-height: 40px;
    padding: 0;
  }

  .nochoice {
    margin: 0;
    padding: 14px;
    border: 1px dashed var(--line);
    border-radius: 12px;
    color: var(--muted);
    font-size: 14px;
    text-align: center;
  }

  .nochoice.bad {
    border-color: var(--danger);
    color: var(--danger);
    font-weight: 600;
  }

  .picker {
    display: flex;
    flex-direction: column;
    gap: 8px;
    border-top: 1px solid var(--line);
    padding-top: 16px;
  }

  .flabel {
    font-weight: 600;
    font-size: 14px;
  }

  .rcount {
    margin: 0;
    font-size: 13px;
    color: var(--muted);
  }

  .results {
    border: 1px solid var(--line);
    border-radius: 12px;
    overflow: hidden;
  }

  .rgroup {
    margin: 0;
    padding: 8px 14px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--muted);
    background: var(--bg);
    border-bottom: 1px solid var(--line);
  }

  .rlist {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .rlist li + li,
  .rlist + .rgroup {
    border-top: 1px solid var(--line);
  }

  .res {
    width: 100%;
    border: 0;
    border-radius: 0;
    background: transparent;
    display: grid;
    grid-template-columns: 30px minmax(0, 1fr) auto;
    gap: 12px;
    align-items: center;
    justify-items: start;
    text-align: left;
    font-weight: 400;
    padding: 8px 14px;
    min-height: 56px;
  }

  .res:hover:not(:disabled) {
    background: var(--bg);
  }

  .res:disabled {
    opacity: 1;
    cursor: default;
  }

  .add {
    justify-self: end;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-weight: 600;
    font-size: 14px;
    color: var(--accent);
  }

  .res:disabled .add {
    color: var(--muted);
  }

  @media (max-width: 600px) {
    .choice.editable {
      grid-template-columns: 28px 30px minmax(0, 1fr);
    }
  }
</style>
