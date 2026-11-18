<script lang="ts">
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import { describeError } from "#lib/api/errors.ts";
  import { editRequest, getRequest, type PrintRequest } from "#lib/api/requests.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import RequestFormView from "#lib/components/requests/RequestFormView.svelte";
  import { editBody, formFrom, type RequestForm } from "#lib/requests/form.ts";
  import { whyNoEdit } from "#lib/requests/access.ts";
  import { loadOptions, type LoadedOptions } from "#lib/requests/load-options.ts";

  const id = $derived(Number(page.params.id));

  let request = $state<PrintRequest | null>(null);
  let loaded = $state<LoadedOptions | null>(null);
  let failure = $state<string | null>(null);

  $effect(() => {
    request = null;
    failure = null;
    if (!Number.isInteger(id) || id <= 0) {
      failure = "Not found. It may have been removed.";
      return;
    }
    Promise.all([getRequest(id), loadOptions()]).then(
      ([found, options]) => {
        request = found;
        loaded = options;
      },
      (error) => (failure = describeError(error)),
    );
  });

  async function save(form: RequestForm): Promise<void> {
    await editRequest(id, editBody(form));
    await goto(`/requests/${id}`);
  }
</script>

<svelte:head><title>Edit request · RollCall</title></svelte:head>

{#if failure}
  <p role="alert" class="error">{failure}</p>
{:else if !request || !loaded}
  <p class="muted">Loading…</p>
{:else if !request.can_edit}
  <div class="page">
    <h1>Edit request</h1>
    <p role="alert" class="error">{whyNoEdit(session.user, request)}</p>
    <a href="/requests/{request.id}">Back to the request</a>
  </div>
{:else}
  <RequestFormView
    initial={formFrom(request)}
    editing={{ id: request.id }}
    options={loaded.options}
    optionsFailure={loaded.failure}
    onsave={save}
  />
{/if}
