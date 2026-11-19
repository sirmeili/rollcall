<script lang="ts">
  import type { Priority } from "#lib/api/requests.ts";
  import { PRIORITY_LABELS } from "#lib/requests/labels.ts";
  import "#lib/requests/requests.css";

  let { priority }: { priority: Priority } = $props();
</script>

<span class="tagchip pri-{priority}"
  ><span class="sr-only">Priority:</span> {PRIORITY_LABELS[priority]}</span
>
