import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});

/**
 * jsdom ships `<dialog>` but not `showModal()`, `close()`, or the Escape
 * handling the platform gives a modal dialog, so a component that opens a real
 * dialog throws on mount and never closes under test.
 *
 * The app's `Modal` is built on the native element on purpose — it is what
 * gives the dialog its focus trap, its top layer and the inert background.
 * Stubbing the component to a plain `<div>` in tests would mean testing
 * something the browser never runs, so the gap is filled here instead: enough
 * of the platform's contract for a test to open a dialog, press Escape and
 * watch it close, the way a person would.
 */
if (typeof HTMLDialogElement !== "undefined" && !HTMLDialogElement.prototype.showModal) {
  const escapeHandlers = new WeakMap<HTMLDialogElement, (event: KeyboardEvent) => void>();

  function close(this: HTMLDialogElement, returnValue?: string) {
    if (!this.open) return;
    this.open = false;
    if (returnValue !== undefined) this.returnValue = returnValue;

    const handler = escapeHandlers.get(this);
    if (handler) {
      document.removeEventListener("keydown", handler);
      escapeHandlers.delete(this);
    }
    this.dispatchEvent(new Event("close"));
  }

  HTMLDialogElement.prototype.show = function show(this: HTMLDialogElement) {
    this.open = true;
  };

  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.open = true;

    // Escape on an open modal fires a cancelable `cancel`; only if nothing
    // calls `preventDefault()` does the dialog actually close. `Modal` does
    // prevent it and closes through React state instead, which is what keeps
    // the `open` prop and the DOM from disagreeing.
    const handler = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || !this.open) return;
      event.preventDefault();
      const cancelled = !this.dispatchEvent(new Event("cancel", { cancelable: true }));
      if (!cancelled) close.call(this);
    };
    escapeHandlers.set(this, handler);
    document.addEventListener("keydown", handler);
  };

  HTMLDialogElement.prototype.close = close;
}
