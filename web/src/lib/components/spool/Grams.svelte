<script lang="ts">
  import { describeError } from "#lib/api/errors.ts";
  import { problemsOf } from "#lib/api/requests.ts";
  import type { SpoolChanges } from "#lib/api/stock.ts";
  import type { SpoolDetail } from "#lib/api/types.ts";
  import { aboutGrams } from "#lib/spools.ts";

  /** Net weight and grams left: estimates, edited in place by Admins (ADR-0019). Then the
   * grams held and available, and for Editors and Admins the requests holding the spool. */
  interface Props {
    spool: SpoolDetail;
    canEdit: boolean;
    onsave: (changes: SpoolChanges) => Promise<void>;
  }

  let { spool, canEdit, onsave }: Props = $props();

  // Edited copies, reset when another spool is shown. Empty inputs bind as null.
  let net = $state<number | null>(null);
  let left = $state<number | null>(null);
  let busy = $state(false);
  let message = $state<string | null>(null);
  let problems = $state<Record<string, string>>({});

  $effect.pre(() => {
    net = spool.net_weight_g;
    left = spool.grams_left_g;
  });

  const dirty = $derived(net !== spool.net_weight_g || left !== spool.grams_left_g);

  async function save(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    busy = true;
    message = null;
    problems = {};
    // Unknown grams left stays unknown unless a figure is typed.
    const changes: SpoolChanges = { net_weight_g: net };
    if (left !== null) changes.grams_left_g = left;
    try {
      await onsave(changes);
      message = "Saved grams";
    } catch (error) {
      const found = problemsOf(error);
      if (found) problems = found;
      else message = describeError(error);
    } finally {
      busy = false;
    }
  }
</script>

<section class="card" aria-labelledby="grams-h">
  <h2 id="grams-h" class="label">Grams</h2>
  {#if canEdit}
    <!-- The server checks the ranges and says what is wrong beside each field. -->
    <form novalidate onsubmit={save}>
      <label>
        Net weight (g)
        <input type="number" min="1" max="10000" step="1" bind:value={net} />
        {#if problems.net_weight_g}<span class="problem">{problems.net_weight_g}</span>{/if}
      </label>
      <label>
        Grams left (g)
        <input
          type="number"
          min="0"
          max={net ?? undefined}
          step="1"
          placeholder="unknown"
          bind:value={left}
        />
        {#if problems.grams_left_g}<span class="problem">{problems.grams_left_g}</span>{/if}
      </label>
      <p class="muted">Changes here aren't in the history and can't be undone.</p>
      <div class="row">
        <button type="submit" disabled={busy || !dirty}>Save grams</button>
        {#if message}<span role="status" class="muted">{message}</span>{/if}
      </div>
    </form>
  {:else}
    <dl>
      <dt>Net weight</dt>
      <dd>{aboutGrams(spool.net_weight_g)}</dd>
      <dt>Grams left</dt>
      <dd>{aboutGrams(spool.grams_left_g)}</dd>
    </dl>
  {/if}
  <dl>
    <dt>Held</dt>
    <dd>{aboutGrams(spool.held_g)}</dd>
    <dt>Available</dt>
    <dd>
      {aboutGrams(spool.available_g)}
      {#if spool.over_held}<span class="notice">Over-held: more is held than is left.</span>{/if}
    </dd>
    {#if spool.holding_requests?.length}
      <dt>Held for</dt>
      <dd>
        <ul>
          {#each spool.holding_requests as request (request.id)}
            <li><a href="/requests/{request.id}">{request.title}</a></li>
          {/each}
        </ul>
      </dd>
    {/if}
  </dl>
</section>

<style>
  form,
  dl {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin: 0;
  }

  label,
  dt {
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 13px;
    font-weight: 600;
    color: var(--muted);
  }

  dd {
    margin: -8px 0 0;
  }

  .notice {
    display: block;
    margin-top: 4px;
    font-size: 13px;
  }

  ul {
    margin: 0;
    padding-left: 18px;
  }

  p {
    margin: 0;
    font-size: 13px;
  }

  .problem {
    color: var(--danger);
    font-weight: 400;
  }

  .row {
    display: flex;
    align-items: center;
    gap: 12px;
  }
</style>
