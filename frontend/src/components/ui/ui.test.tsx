import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Alert, Badge, Button, FormField, Input, Select, Textarea } from "@/components/ui";

/**
 * These assert the contracts the design system promises — the accessible
 * wiring, the disabled and busy semantics, the announcement roles — not the
 * Tailwind classes that implement them. A test that asserts `bg-primary` fails
 * the moment the brand changes, which is the opposite of what this refactor
 * was for.
 */

describe("Button", () => {
  it("defaults to type=button so it cannot submit a form it was only sitting in", () => {
    render(
      <form>
        <Button>Click</Button>
      </form>,
    );
    expect(screen.getByRole("button")).toHaveAttribute("type", "button");
  });

  it("still accepts an explicit submit type", () => {
    render(<Button type="submit">Save</Button>);
    expect(screen.getByRole("button")).toHaveAttribute("type", "submit");
  });

  it("disables itself while loading and says so", () => {
    render(<Button loading>Save</Button>);
    const button = screen.getByRole("button");
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
  });

  it("does not claim to be busy when it is merely disabled", () => {
    render(<Button disabled>Save</Button>);
    expect(screen.getByRole("button")).not.toHaveAttribute("aria-busy");
  });

  it("keeps its label visible while loading, so the control does not resize", () => {
    render(<Button loading>Save changes</Button>);
    expect(screen.getByRole("button", { name: /save changes/i })).toBeInTheDocument();
  });

  it("does not fire onClick once disabled", async () => {
    const onClick = vi.fn();
    render(
      <Button disabled onClick={onClick}>
        Click
      </Button>,
    );
    await userEvent.click(screen.getByRole("button"), { pointerEventsCheck: 0 });
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe("FormField", () => {
  it("ties the label to the control it labels", () => {
    render(
      <FormField label="Email">
        <Input />
      </FormField>,
    );
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
  });

  it("leaves the required marker out of the accessible name", () => {
    render(
      <FormField label="Email" required>
        <Input />
      </FormField>,
    );
    // "Email", not "Email *" — the asterisk is decoration, `required` is the
    // thing that actually carries the requirement.
    expect(screen.getByLabelText("Email")).toBeRequired();
  });

  it("describes the control with its hint", () => {
    render(
      <FormField label="Address" hint="Used for recruiter matching">
        <Input />
      </FormField>,
    );
    expect(screen.getByLabelText("Address")).toHaveAccessibleDescription("Used for recruiter matching");
  });

  it("marks the control invalid and describes it with the error", () => {
    render(
      <FormField label="Email" error="That address is not valid">
        <Input />
      </FormField>,
    );
    const input = screen.getByLabelText("Email");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("That address is not valid");
  });

  it("replaces the hint with the error rather than announcing both", () => {
    render(
      <FormField label="Email" hint="We never share it" error="That address is not valid">
        <Input />
      </FormField>,
    );
    expect(screen.getByLabelText("Email")).toHaveAccessibleDescription("That address is not valid");
  });

  it("respects an id the caller already set on the control", () => {
    render(
      <FormField label="Email">
        <Input id="my-email" />
      </FormField>,
    );
    expect(screen.getByLabelText("Email")).toHaveAttribute("id", "my-email");
  });

  it("labels a textarea and a select the same way it labels an input", () => {
    render(
      <>
        <FormField label="Notes">
          <Textarea />
        </FormField>
        <FormField label="Role">
          <Select>
            <option value="a">A</option>
          </Select>
        </FormField>
      </>,
    );
    expect(screen.getByLabelText("Notes")).toBeInTheDocument();
    expect(screen.getByLabelText("Role")).toBeInTheDocument();
  });
});

describe("Alert", () => {
  it("interrupts for a failure", () => {
    render(<Alert tone="danger">Something broke</Alert>);
    expect(screen.getByRole("alert")).toHaveTextContent("Something broke");
  });

  it("does not interrupt for a confirmation", () => {
    render(<Alert tone="success">Saved</Alert>);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Saved");
  });

  it("hides its glyph from assistive tech, since the tone already carries it", () => {
    const { container } = render(<Alert tone="warning">Careful</Alert>);
    expect(container.querySelector("[aria-hidden='true']")).toBeInTheDocument();
  });
});

describe("Badge", () => {
  it("renders its content as text rather than interpreting it", () => {
    render(<Badge>{"<script>"}</Badge>);
    expect(screen.getByText("<script>")).toBeInTheDocument();
  });
});
