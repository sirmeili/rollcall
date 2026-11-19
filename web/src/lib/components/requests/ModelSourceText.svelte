<script lang="ts">
  /** Where a request's model is: File, Link, File and link, or Notes only. */
  import type { ModelSource } from "#lib/api/requests.ts";
  import { MODEL_TEXT } from "#lib/requests/labels.ts";

  let { model }: { model: ModelSource } = $props();
</script>

<span class="src">
  <svg
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2.2"
    stroke-linecap="round"
    aria-hidden="true"
  >
    {#if model === "link"}
      <path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1"></path>
      <path d="M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"></path>
    {:else if model === "notes"}
      <path d="M4 6h16M4 12h16M4 18h10"></path>
    {:else}
      <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path>
      <path d="M14 3v6h6"></path>
    {/if}
  </svg>{MODEL_TEXT[model]}
</span>

<style>
  .src {
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }
</style>
