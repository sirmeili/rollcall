<script lang="ts">
  import { describeError } from "#lib/api/errors.ts";
  import { getEmailStatus, type EmailStatus } from "#lib/api/settings.ts";
  import { dateTime } from "#lib/format.ts";

  /** The email sender's last success and failure since the server started. Read again
   * whenever `version` changes (after a test email). */
  interface Props {
    version: number;
  }

  let { version }: Props = $props();

  let status = $state<EmailStatus | null>(null);
  let failure = $state<string | null>(null);

  async function load(): Promise<void> {
    try {
      status = await getEmailStatus();
      failure = null;
    } catch (error) {
      failure = describeError(error);
    }
  }

  $effect(() => {
    void version;
    void load();
  });
</script>

<div class="status" aria-label="Email status" role="group">
  {#if failure}
    <p role="alert" class="error">{failure}</p>
  {:else if status}
    {#if !status.on}
      <p class="muted">Email is off until an SMTP host is set.</p>
    {/if}
    {#if status.last_success}
      <p>Last sent {dateTime(status.last_success)}</p>
    {/if}
    {#if status.last_failure}
      <p class="failed">
        Last failure {dateTime(status.last_failure.at)}: {status.last_failure.message}
      </p>
    {/if}
    {#if status.on && !status.last_success && !status.last_failure}
      <p class="muted">Nothing sent since the server started.</p>
    {/if}
  {/if}
</div>

<style>
  .status {
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 14px;
  }

  p {
    margin: 0;
  }

  .failed {
    color: var(--lowtext);
  }
</style>
