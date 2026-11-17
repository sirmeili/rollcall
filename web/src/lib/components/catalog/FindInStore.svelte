<script lang="ts">
  /** Find in store: the store's search for a catalog color, in a new tab. */
  interface Props {
    /** From storeUrl(). */
    href: string;
  }

  let { href }: Props = $props();
</script>

<a class="button store" {href} target="_blank" rel="noopener noreferrer"
  >Find in store<svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2.2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    ><path d="M14 4h6v6M20 4l-9 9"></path><path
      d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"
    ></path></svg
  >{" "}<span class="sr-only">(opens in a new tab)</span></a
>

<style>
  .store {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    align-self: flex-start;
  }
</style>
