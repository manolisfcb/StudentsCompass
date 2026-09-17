import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});

/**
 * jsdom ships `<dialog>` but not `showModal()`/`close()`, so a component that
 * opens a real dialog throws on mount under test.
 *
 * The app's `Modal` is built on the native element on purpose — it is what
 * gives the dialog its focus trap, its Escape handling, its top layer and the
 * inert background. Stubbing the component to a plain `<div>` in tests would
 * mean testing something the browser never runs, so the gap is filled here
 * instead: enough of the contract for a test to open a dialog, read it and
 * close it.
 */
if (typeof HTMLDialogElement !== "undefined" && !HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.show = function show(this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement, returnValue?: string) {
    this.open = false;
    if (returnValue !== undefined) this.returnValue = returnValue;
    this.dispatchEvent(new Event("close"));
  };
}
