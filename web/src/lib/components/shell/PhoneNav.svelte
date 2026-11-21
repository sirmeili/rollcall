<script lang="ts">
  // The phone layout's bottom bar (docs/mockups/mobile-web/): Menu at the left, the page's
  // action in the centre (see phoneCentre) and the signed-in user at the right, who opens Account.
  import type { Me } from "#lib/api/types.ts";
  import ScanIcon from "#lib/components/phone/ScanIcon.svelte";
  import MenuSheet from "#lib/components/shell/MenuSheet.svelte";
  import { newUserForm } from "#lib/new-user-form.svelte.ts";
  import {
    ACCOUNT_PATH,
    menuActions,
    menuGroups,
    NEW_REQUEST_PATH,
    NEW_SPOOL_PATH,
    navItemFor,
    phoneCentre,
  } from "#lib/nav.ts";

  interface Props {
    user: Me;
    pathname: string;
    reviewCount: number;
    /** Submitted print requests, for Editors and Admins. */
    requestCount?: number;
    /** Scan is available: running as the Android app, paired. */
    scan?: boolean;
  }

  let { user, pathname, reviewCount, requestCount = 0, scan = false }: Props = $props();

  let open = $state(false);
  let menuButton: HTMLButtonElement;
  const groups = $derived(menuGroups(user));
  const actions = $derived(menuActions(user, scan));
  const centre = $derived(phoneCentre(user, pathname, scan));

  /** Close the menu and give the focus back to the Menu button. */
  function close(): void {
    open = false;
    menuButton.focus();
  }

  // A new page closes the menu.
  $effect(() => {
    void pathname;
    open = false;
  });
</script>

<!-- The plus on the add buttons. -->
{#snippet plus(size: number)}
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2.6"
    stroke-linecap="round"
    aria-hidden="true"><path d="M12 5v14M5 12h14"></path></svg
  >
{/snippet}

{#if open}
  <MenuSheet
    {actions}
    main={groups.main}
    admin={groups.admin}
    current={navItemFor(pathname)}
    badges={{ "/review": reviewCount, "/requests": requestCount }}
    onclose={close}
  />
{/if}

<nav aria-label="App" class="bar">
  <button
    type="button"
    class="end start"
    aria-expanded={open}
    aria-controls="menu-sheet"
    bind:this={menuButton}
    onclick={() => (open ? close() : (open = true))}
  >
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2.2"
      stroke-linecap="round"
      aria-hidden="true"
    >
      {#if open}
        <path d="M6 6l12 12M18 6 6 18"></path>
      {:else}
        <path d="M4 7h16M4 12h16M4 17h16"></path>
      {/if}
    </svg>
    {open ? "Close" : "Menu"}
    {#if reviewCount + requestCount > 0 && !open}<span class="dot" aria-hidden="true"></span>{/if}
  </button>

  {#if centre === "scan"}
    <a class="scan" href="/scan"
      ><span class="fab" aria-hidden="true"><ScanIcon size={30} /></span>Scan</a
    >
  {:else if centre === "scan-and-add-spool"}
    <!-- Option b2 in #171's mockup: Scan stays the big button, Add spool a smaller one beside it. -->
    <div class="pair">
      <a class="scan" href="/scan"
        ><span class="fab" aria-hidden="true"><ScanIcon size={30} /></span>Scan</a
      >
      <a class="side" href={NEW_SPOOL_PATH}><span class="disc">{@render plus(20)}</span>Add spool</a
      >
    </div>
  {:else if centre === "add-spool"}
    <a class="scan" href={NEW_SPOOL_PATH}><span class="fab">{@render plus(30)}</span>Add spool</a>
  {:else if centre === "new-request"}
    <a class="scan" href={NEW_REQUEST_PATH}
      ><span class="fab">{@render plus(30)}</span>New request</a
    >
  {:else if centre === "new-user"}
    <!-- Opens the Users page's own new-user form. -->
    <button type="button" class="scan" onclick={() => (newUserForm.open = true)}
      ><span class="fab">{@render plus(30)}</span>New user</button
    >
  {:else}
    <span></span>
  {/if}

  <a
    class="end finish"
    href={ACCOUNT_PATH}
    aria-current={pathname === ACCOUNT_PATH ? "page" : undefined}
  >
    <span class="initial" aria-hidden="true">{user.username.charAt(0).toUpperCase()}</span>
    {user.username}
  </a>
</nav>

<style>
  .bar {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 42;
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: end;
    padding: 8px 14px calc(14px + env(safe-area-inset-bottom, 0px));
    border-top: 1px solid var(--line);
    background: var(--surface);
  }

  .end {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    min-width: 64px;
    min-height: 48px;
    padding: 0 6px;
    border: 0;
    background: transparent;
    color: var(--muted);
    font-size: 12px;
    font-weight: 600;
  }

  .start {
    justify-self: start;
  }

  .finish {
    justify-self: end;
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .end[aria-expanded="true"],
  .end[aria-current="page"] {
    color: var(--text);
  }

  .dot {
    position: absolute;
    top: 4px;
    right: 18px;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent);
  }

  .scan {
    min-height: 0;
    padding: 0;
    border: 0;
    border-radius: 0;
    background: transparent;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    margin-top: -30px;
    color: var(--text);
    font-size: 12px;
    font-weight: 700;
  }

  .fab {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--accent);
    color: var(--onaccent);
    box-shadow:
      0 0 0 5px var(--surface),
      0 4px 14px rgba(0, 0, 0, 0.25);
  }

  .pair {
    display: flex;
    align-items: flex-end;
    gap: 10px;
    margin-top: -30px;
  }

  .pair .scan {
    margin-top: 0;
  }

  .side {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    color: var(--muted);
    font-size: 11px;
    font-weight: 700;
  }

  .disc {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--chip);
    color: var(--text);
    box-shadow: 0 0 0 4px var(--surface);
  }

  .initial {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--chip);
    color: var(--text);
    font-size: 13px;
    font-weight: 700;
  }

  .end[aria-current="page"] .initial {
    background: var(--text);
    color: var(--bg);
  }
</style>
