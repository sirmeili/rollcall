<script lang="ts">
  /** A request's status. Submitted is the only one until requests are worked (issue #76). */
  import type { RequestStatus } from "#lib/api/requests.ts";
  import "#lib/requests/requests.css";

  let { status }: { status: RequestStatus } = $props();
</script>

<span class="tagchip st-{status}">Submitted</span>
