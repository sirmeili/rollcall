<script lang="ts">
  import {
    acceptEvent,
    dismissLikelyEmpty,
    dismissTag,
    getReview,
    keepSeparate,
    restoreDuplicate,
    restoreLikelyEmpty,
    restoreTag,
    sameProduct,
    unacceptEvent,
  } from "#lib/api/admin.ts";
  import { describeError } from "#lib/api/errors.ts";
  import { recordAction, undoEvent, waitingIn } from "#lib/api/stock.ts";
  import type {
    EventOut,
    PossibleDuplicate,
    Product,
    ReviewOut,
    SpoolRow,
    UnidentifiedTag,
  } from "#lib/api/types.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import ReviewItem from "#lib/components/review/ReviewItem.svelte";
  import ReviewSection from "#lib/components/review/ReviewSection.svelte";
  import UndoBanner from "#lib/components/ui/UndoBanner.svelte";
  import { dateTime, eventBy, eventTitle, shortDate } from "#lib/format.ts";
  import { flaggedText, spoolName, tagText } from "#lib/review.ts";
  import { reviewBadge } from "#lib/review-badge.svelte.ts";

  interface Done {
    message: string;
    /** Reverses the change, for Bring back; absent when it cannot be reversed. */
    bringBack?: () => Promise<unknown>;
  }

  let review = $state<ReviewOut | null>(null);
  let failure = $state<string | null>(null);
  let done = $state<Done | null>(null);
  let problem = $state<string | null>(null);
  let busy = $state(false);

  const canEdit = $derived(session.can("editor"));

  async function load(): Promise<void> {
    try {
      review = await getReview();
      reviewBadge.count = waitingIn(review);
      failure = null;
    } catch (error) {
      failure = describeError(error);
    }
  }

  $effect(() => {
    void load();
  });

  /** Run a change, show what happened, and reload. */
  async function act(change: () => Promise<unknown>, result: Done): Promise<void> {
    busy = true;
    problem = null;
    try {
      await change();
      done = result;
      await load();
    } catch (error) {
      problem = describeError(error);
    } finally {
      busy = false;
    }
  }

  function accept(event: EventOut): Promise<void> {
    return act(() => acceptEvent(event.id), {
      message: `Accepted “${eventTitle(event.type)}” on ${spoolName(event)}.`,
      bringBack: () => unacceptEvent(event.id),
    });
  }

  function undo(event: EventOut): Promise<void> {
    // An undo cannot be brought back: undoing an undo is refused.
    return act(() => undoEvent(event.id), {
      message: `Undid “${eventTitle(event.type)}” on ${spoolName(event)}.`,
    });
  }

  function dismiss(tag: UnidentifiedTag): Promise<void> {
    return act(() => dismissTag(tag.uid), {
      message: `Dismissed the ${tagText(tag).title.toLowerCase()}.`,
      bringBack: () => restoreTag(tag.uid),
    });
  }

  function markUsedUp(spool: SpoolRow): Promise<void> {
    return act(() => recordAction(spool.id, "empty"), {
      message: `Marked ${spool.product.display_name} #${spool.id} used up.`,
    });
  }

  function dismissSuggestion(spool: SpoolRow): Promise<void> {
    return act(() => dismissLikelyEmpty(spool.id), {
      message: `Dismissed the suggestion for ${spool.product.display_name} #${spool.id}.`,
      bringBack: () => restoreLikelyEmpty(spool.id),
    });
  }

  function same(duplicate: PossibleDuplicate, candidate: Product): Promise<void> {
    // The candidate is deleted, so Same product cannot be brought back.
    return act(() => sameProduct(duplicate.id, candidate.id), {
      message: `Made ${duplicate.product.display_name} and ${candidate.display_name} one product.`,
    });
  }

  function separate(duplicate: PossibleDuplicate): Promise<void> {
    return act(() => keepSeparate(duplicate.id), {
      message: `Kept ${duplicate.product.display_name} separate.`,
      bringBack: () => restoreDuplicate(duplicate.id),
    });
  }

  async function bringBack(): Promise<void> {
    const reverse = done?.bringBack;
    if (!reverse) return;
    await act(reverse, { message: "Brought back to Review." });
  }
</script>

<svelte:head><title>Review · RollCall</title></svelte:head>

<div class="page">
  <div class="pagehead">
    <div>
      <h1>Review</h1>
      <p>Things the system recorded but wants a person to check.</p>
    </div>
  </div>

  {#if done}
    <UndoBanner
      message={done.message}
      actionLabel={done.bringBack ? "Bring back" : undefined}
      {busy}
      onaction={bringBack}
    />
  {/if}
  {#if problem}<p role="alert" class="error">{problem}</p>{/if}

  {#if failure}
    <p role="alert" class="error">{failure}</p>
  {:else if !review}
    <p class="muted">Loading…</p>
  {:else}
    <ReviewSection
      id="flagged-h"
      title="Flagged events"
      count={review.flagged_events.length}
      empty="Nothing flagged."
    >
      {#each review.flagged_events as event (event.id)}
        {@const text = flaggedText(event)}
        <ReviewItem rgba={event.color_rgba} title={text.title} body={text.body}>
          {#snippet meta()}
            <a href="/spools/{event.spool_id}">{spoolName(event)}</a> ·
            <span class="mono">{dateTime(event.occurred_at)}</span> · {eventBy(event)}
          {/snippet}
          {#snippet actions()}
            {#if canEdit}
              <button
                type="button"
                class="primary"
                disabled={busy}
                aria-label="Accept {eventTitle(event.type)} on {spoolName(event)}"
                onclick={() => accept(event)}>Accept</button
              >
              <button
                type="button"
                disabled={busy}
                aria-label="Undo {eventTitle(event.type)} on {spoolName(event)}"
                onclick={() => undo(event)}>Undo</button
              >
            {/if}
            <a class="button" href="/spools/{event.spool_id}">Open spool</a>
          {/snippet}
        </ReviewItem>
      {/each}
    </ReviewSection>

    <ReviewSection
      id="tags-h"
      title="Unidentified tags"
      count={review.unidentified_tags.length}
      empty="No unidentified tags."
    >
      {#each review.unidentified_tags as tag (tag.uid)}
        {@const text = tagText(tag)}
        <ReviewItem title={text.title} body={text.body}>
          {#snippet meta()}
            First seen <span class="mono">{dateTime(tag.first_seen_at)}</span>
          {/snippet}
          {#snippet actions()}
            {#if canEdit}
              <button
                type="button"
                disabled={busy}
                aria-label="Dismiss the tag first seen {dateTime(tag.first_seen_at)}"
                onclick={() => dismiss(tag)}>Dismiss</button
              >
            {/if}
          {/snippet}
        </ReviewItem>
      {/each}
    </ReviewSection>

    <ReviewSection
      id="likely-h"
      title="Likely empty"
      count={review.likely_empty.length}
      empty="No suggestions. The printer suggests a spool here when its AMS reports 0% left."
    >
      {#each review.likely_empty as spool (spool.id)}
        <ReviewItem
          rgba={spool.product.color_rgba}
          title="AMS reports {spool.remaining_pct ?? 0}% left"
          body="The printer suggests this spool is used up."
        >
          {#snippet meta()}
            <a href="/spools/{spool.id}">{spool.product.display_name} #{spool.id}</a> · opened
            {shortDate(spool.opened_at)}
          {/snippet}
          {#snippet actions()}
            {#if canEdit}
              <button
                type="button"
                class="primary"
                disabled={busy}
                onclick={() => markUsedUp(spool)}>Mark used up</button
              >
              <button
                type="button"
                disabled={busy}
                aria-label="Dismiss the suggestion for {spool.product.display_name} #{spool.id}"
                onclick={() => dismissSuggestion(spool)}>Dismiss</button
              >
            {/if}
          {/snippet}
        </ReviewItem>
      {/each}
    </ReviewSection>

    <ReviewSection
      id="duplicates-h"
      title="Possible duplicates"
      count={review.possible_duplicates.length}
      empty="No possible duplicates."
    >
      {#each review.possible_duplicates as duplicate (duplicate.id)}
        {@const name = duplicate.product.display_name}
        <ReviewItem
          rgba={duplicate.product.color_rgba}
          title={name}
          body="A scan made this product, and it may be the same as a “From the catalog” product."
        >
          {#snippet meta()}
            May be: {duplicate.candidates.map((c) => c.display_name).join(", ")} · scanned
            <span class="mono">{dateTime(duplicate.created_at)}</span>
          {/snippet}
          {#snippet actions()}
            {#if canEdit}
              {#each duplicate.candidates as candidate (candidate.id)}
                <button
                  type="button"
                  class="primary"
                  disabled={busy}
                  aria-label="Same product as {candidate.display_name}"
                  onclick={() => same(duplicate, candidate)}>Same product</button
                >
              {/each}
              <button
                type="button"
                disabled={busy}
                aria-label="Keep {name} separate"
                onclick={() => separate(duplicate)}>Keep separate</button
              >
            {/if}
          {/snippet}
        </ReviewItem>
      {/each}
    </ReviewSection>
  {/if}
</div>

<style>
  .page {
    gap: 28px;
  }

  :global(article .meta a) {
    text-decoration: underline;
  }
</style>
