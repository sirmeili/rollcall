<script lang="ts">
  /** A filament choice's grams and holds, once approved. Editors and Admins see its grams,
   * each hold (spool and grams) and what is short; anyone else gets only whether it is held
   * (`held`) and sees "Held" or "Waiting on filament". Nothing shows before Approve, or once
   * the request has left the statuses that hold filament. */
  import type { Choice } from "#lib/api/requests.ts";

  interface Props {
    choice: Choice;
  }

  let { choice }: Props = $props();

  /** "About 900 g", with what is short when anything is. */
  function gramsText(grams: number | null, short: number): string {
    return short > 0 ? `About ${grams} g · short ${short} g` : `About ${grams} g`;
  }
</script>

{#if choice.held !== null}
  {#if choice.holds === null || choice.short_g === null}
    <span class="holds">{choice.held ? "Held" : "Waiting on filament"}</span>
  {:else}
    <span class="holds">
      <span>{gramsText(choice.grams, choice.short_g)}</span>
      {#if choice.holds.length}
        <ul aria-label={`Holds for ${choice.name}`}>
          {#each choice.holds as hold (hold.spool_id)}
            <li>
              <a href={`/spools/${hold.spool_id}`}>{`Spool #${hold.spool_id}`}</a>
              {`${hold.product_name} · about ${hold.grams} g`}
            </li>
          {/each}
        </ul>
      {:else}
        <span class="none">Nothing held</span>
      {/if}
    </span>
  {/if}
{/if}

<style>
  .holds {
    display: flex;
    flex-direction: column;
    gap: 2px;
    margin-top: 4px;
    font-size: 13px;
  }

  ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .none {
    color: var(--muted);
  }
</style>
