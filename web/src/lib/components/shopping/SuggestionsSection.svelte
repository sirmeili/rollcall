<script lang="ts">
  /** The Suggestions section at the top of the shopping list: what Viewers asked to buy,
   * counting toward nothing. Editors and Admins Add each one, making it a hand-added reason,
   * or Dismiss it. */
  import type { Suggestion } from "#lib/api/shopping.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import HexRing from "#lib/components/catalog/HexRing.svelte";
  import { suggestionHexes, suggestionName, suggestionText } from "#lib/shopping-list.ts";

  interface Props {
    suggestions: Suggestion[];
    /** Add or dismiss a suggestion, by its ID. */
    onadd: (id: number) => void;
    ondismiss: (id: number) => void;
    /** A decision is being made: the buttons wait. */
    busy: boolean;
  }

  let { suggestions, onadd, ondismiss, busy }: Props = $props();

  const editor = $derived(session.can("editor"));
</script>

<section class="group" aria-labelledby="suggestions-head">
  <h2 class="ghead" id="suggestions-head">
    <span class="gname">Suggestions</span>
    <span class="gmeta">· count toward nothing until added</span>
  </h2>
  <ul class="rows">
    {#each suggestions as suggestion (suggestion.id)}
      {@const name = suggestionName(suggestion)}
      <li>
        <HexRing hexes={suggestionHexes(suggestion)} />
        <span class="text">
          <span class="name">{name}</span>
          <span class="sub">{suggestionText(suggestion)}</span>
        </span>
        {#if editor}
          <span class="actions">
            <button
              type="button"
              class="small"
              aria-label={`Add ${name}`}
              disabled={busy}
              onclick={() => onadd(suggestion.id)}>Add</button
            >
            <button
              type="button"
              class="small"
              aria-label={`Dismiss ${name}`}
              disabled={busy}
              onclick={() => ondismiss(suggestion.id)}>Dismiss</button
            >
          </span>
        {/if}
      </li>
    {/each}
  </ul>
</section>

<style>
  .group {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 16px;
    overflow: hidden;
  }

  .ghead {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px 12px;
    min-height: 56px;
    margin: 0;
    padding: 0 18px;
    font-size: inherit;
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

  .rows {
    margin: 0;
    padding: 0;
    list-style: none;
    border-top: 1px solid var(--line);
  }

  .rows > li {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 8px 14px;
    padding: 12px 18px;
  }

  .rows > li + li {
    border-top: 1px solid var(--line);
  }

  .text {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .name {
    font-weight: 600;
    overflow-wrap: anywhere;
  }

  .sub {
    font-size: 13px;
    color: var(--muted);
    overflow-wrap: anywhere;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  @media (max-width: 600px) {
    .rows > li {
      grid-template-columns: auto minmax(0, 1fr);
      padding: 12px 16px;
    }

    .actions {
      grid-column: 2;
    }
  }
</style>
