<script lang="ts">
  /** A request's status, as the priority chip shows a priority. */
  import type { RequestStatus } from "#lib/api/requests.ts";
  import { STATUS_LABELS } from "#lib/requests/labels.ts";
  import "#lib/requests/requests.css";

  let { status }: { status: RequestStatus } = $props();
</script>

<span class="tagchip st st-{status}"
  ><span class="sr-only">Status:</span> {STATUS_LABELS[status]}</span
>
