<script lang="ts">
  import { goto } from "$app/navigation";
  import { submitRequest } from "#lib/api/requests.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import RequestFormView from "#lib/components/requests/RequestFormView.svelte";
  import { canSubmit } from "#lib/requests/access.ts";
  import { blankForm, requestBody, type RequestForm } from "#lib/requests/form.ts";
  import { loadOptions, type LoadedOptions } from "#lib/requests/load-options.ts";

  let loaded = $state<LoadedOptions | null>(null);
  const allowed = $derived(canSubmit(session.user));

  $effect(() => {
    if (allowed) void loadOptions().then((result) => (loaded = result));
  });

  async function save(form: RequestForm): Promise<void> {
    const created = await submitRequest(requestBody(form));
    if (session.user) session.user.has_requests = true;
    await goto(`/requests/${created.id}`, { replaceState: true });
  }
</script>

<svelte:head><title>New request · RollCall</title></svelte:head>

{#if !allowed}
  <div class="page">
    <h1>New request</h1>
    <p role="alert" class="error">You can no longer submit or edit print requests.</p>
    <a href="/requests">Back to Requests</a>
  </div>
{:else if !loaded}
  <p class="muted">Loading…</p>
{:else}
  <RequestFormView
    initial={blankForm()}
    options={loaded.options}
    optionsFailure={loaded.failure}
    onsave={save}
  />
{/if}
