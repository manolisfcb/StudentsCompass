import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Modal, Tabs, type TabItem } from "@/components/ui";

/**
 * The two components that carry real interaction. `Modal` leans on the native
 * `<dialog>` for its focus trap and Escape handling — jsdom stubs those in
 * `vitest.setup.ts`, so what is asserted here is the wiring around them:
 * that the caller is told to close, and that the dialog follows `open`.
 */

describe("Modal", () => {
  it("is absent from the accessibility tree while closed", () => {
    render(
      <Modal open={false} onClose={() => {}} title="Edit resource">
        <p>Body</p>
      </Modal>,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("exposes itself as a dialog named by its title once open", () => {
    render(
      <Modal open onClose={() => {}} title="Edit resource">
        <p>Body</p>
      </Modal>,
    );
    expect(screen.getByRole("dialog", { name: "Edit resource" })).toBeInTheDocument();
  });

  it("asks the caller to close rather than closing itself", async () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="Edit resource">
        <p>Body</p>
      </Modal>,
    );
    await userEvent.click(screen.getByRole("button", { name: /close/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes on Escape, which the native element reports as a cancel", () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="Edit resource">
        <p>Body</p>
      </Modal>,
    );
    const dialog = screen.getByRole("dialog");
    // `cancel` is what Escape fires; without handling it the dialog would hide
    // while the caller still believed it was open.
    dialog.dispatchEvent(new Event("cancel", { cancelable: true, bubbles: false }));
    expect(onClose).toHaveBeenCalled();
  });

  it("renders footer actions outside the scrolling body", () => {
    render(
      <Modal open onClose={() => {}} title="Edit resource" footer={<button type="button">Save</button>}>
        <p>Body</p>
      </Modal>,
    );
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
  });

  it("keeps a click inside the panel from being read as a backdrop dismiss", async () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="Edit resource">
        <p>Body text</p>
      </Modal>,
    );
    await userEvent.click(screen.getByText("Body text"));
    expect(onClose).not.toHaveBeenCalled();
  });
});

const ITEMS: TabItem[] = [
  { value: "all", label: "All", count: 4 },
  { value: "career", label: "Career", count: 2 },
  { value: "learning", label: "Learning" },
];

function TabsProbe({ onChange }: { onChange?: (value: string) => void }) {
  const [value, setValue] = useState("all");
  return (
    <Tabs
      items={ITEMS}
      value={value}
      label="Filter by category"
      onChange={(next) => {
        setValue(next);
        onChange?.(next);
      }}
    />
  );
}

describe("Tabs", () => {
  it("announces itself as a named tablist rather than a row of buttons", () => {
    render(<TabsProbe />);
    expect(screen.getByRole("tablist", { name: "Filter by category" })).toBeInTheDocument();
    expect(screen.getAllByRole("tab")).toHaveLength(3);
  });

  it("marks exactly one tab selected", () => {
    render(<TabsProbe />);
    const selected = screen.getAllByRole("tab").filter((tab) => tab.getAttribute("aria-selected") === "true");
    expect(selected).toHaveLength(1);
    expect(selected[0]).toHaveAccessibleName(/All/);
  });

  it("puts only the active tab in the tab order, per the roving-tabindex pattern", () => {
    render(<TabsProbe />);
    const [all, career, learning] = screen.getAllByRole("tab");
    expect(all).toHaveAttribute("tabindex", "0");
    expect(career).toHaveAttribute("tabindex", "-1");
    expect(learning).toHaveAttribute("tabindex", "-1");
  });

  it("moves selection with the arrow keys", async () => {
    render(<TabsProbe />);
    await userEvent.click(screen.getByRole("tab", { name: /All/ }));
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: /Career/ })).toHaveAttribute("aria-selected", "true");
  });

  it("wraps from the first tab back to the last", async () => {
    render(<TabsProbe />);
    await userEvent.click(screen.getByRole("tab", { name: /All/ }));
    await userEvent.keyboard("{ArrowLeft}");
    expect(screen.getByRole("tab", { name: /Learning/ })).toHaveAttribute("aria-selected", "true");
  });

  it("reports the chosen value to the caller", async () => {
    const onChange = vi.fn();
    render(<TabsProbe onChange={onChange} />);
    await userEvent.click(screen.getByRole("tab", { name: /Career/ }));
    expect(onChange).toHaveBeenCalledWith("career");
  });

  it("shows a count only for the tabs that carry one", () => {
    render(<TabsProbe />);
    expect(screen.getByRole("tab", { name: /All/ })).toHaveTextContent("4");
    expect(screen.getByRole("tab", { name: /Learning/ })).toHaveTextContent(/^Learning$/);
  });
});
