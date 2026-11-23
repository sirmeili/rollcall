<script lang="ts">
  /** "Leave without saving?": asked before leaving a form with unsaved changes, in the frame
   * of the other dialogs (MoveDialog). Stay is the default; Escape, the dimmed page and the
   * phone's Back all Stay. In the layout, it also watches the page's forms and guards every
   * navigation the person makes: a link, the browser's Back (and the phone's, which is the
   * same), and closing or reloading the tab, which the browser asks about itself. The app's
   * own `goto`s (saving a form, a session that has expired, a revoked phone, the launch
   * redirects) are never asked about. */
  import { beforeNavigate, goto } from "$app/navigation";
  import { keepTabInside } from "#lib/focus-trap.ts";
  import {
    askToLeave,
    forgetChanges,
    hasUnsavedChanges,
    leaveWarning,
    watchForms,
  } from "#lib/leave-warning.svelte.ts";
  import { openLayer } from "#lib/phone/back.ts";

  $effect(() => {
    const unwatch = watchForms();
    return () => {
      unwatch();
      leaveWarning.answer(false);
    };
  });

  beforeNavigate((navigation) => {
    if (navigation.type === "goto" || !hasUnsavedChanges()) {
      forgetChanges();
      return;
    }
    // Leaving the page altogether: cancelling it has the browser ask.
    navigation.cancel();
    if (navigation.type === "leave") return;
    const { to, willUnload } = navigation;
    const delta = navigation.type === "popstate" ? navigation.delta : null;
    void askToLeave().then((leave) => {
      if (!leave) return;
      forgetChanges();
      if (delta !== null) history.go(delta);
      else if (to && willUnload) location.assign(to.url);
      else if (to) void goto(to.url);
    });
  });

  // The warning is a layer itself: the phone's Back on it Stays.
  $effect(() => {
    if (leaveWarning.open) return openLayer(() => leaveWarning.answer(false));
  });

  let box = $state<HTMLDivElement>();

  $effect(() => {
    box?.querySelector<HTMLElement>("button.stay")?.focus();
  });

  /** Escape Stays; Tab stays inside the dialog. */
  function keydown(event: KeyboardEvent): void {
    if (event.key === "Escape") {
      event.preventDefault();
      leaveWarning.answer(false);
      return;
    }
    keepTabInside(box!, event);
  }
</script>

{#if leaveWarning.open}
  <button
    type="button"
    class="dim"
    aria-label="Stay"
    tabindex="-1"
    onclick={() => leaveWarning.answer(false)}
  ></button>
  <div
    class="leavedlg"
    role="alertdialog"
    aria-modal="true"
    aria-labelledby="leave-title"
    aria-describedby="leave-text"
    tabindex="-1"
    bind:this={box}
    onkeydown={keydown}
  >
    <div class="top">
      <h2 id="leave-title">Leave without saving?</h2>
    </div>
    <p class="body" id="leave-text">Your changes will be lost.</p>
    <div class="foot">
      <button type="button" onclick={() => leaveWarning.answer(true)}>Leave</button>
      <button type="button" class="primary stay" onclick={() => leaveWarning.answer(false)}
        >Stay</button
      >
    </div>
  </div>
{/if}

<style>
  .dim {
    position: fixed;
    inset: 0;
    z-index: 50;
    border: 0;
    border-radius: 0;
    background: rgba(28, 27, 25, 0.45);
  }

  .leavedlg {
    position: fixed;
    z-index: 51;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: min(420px, calc(100vw - 32px));
    border: 1px solid var(--line);
    border-radius: 16px;
    background: var(--surface);
    color: var(--text);
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  }

  .top {
    padding: 20px 22px 14px;
    border-bottom: 1px solid var(--line);
  }

  h2 {
    margin: 0;
    font-family: var(--font-head);
    font-size: 22px;
  }

  .body {
    margin: 0;
    padding: 16px 22px;
  }

  .foot {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    padding: 14px 22px 18px;
    border-top: 1px solid var(--line);
  }
</style>
