import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DataTable, EmptyState, LoadingState, ProgressBar, Spinner, StatCard, type Column } from "@/components/ui";

describe("ProgressBar", () => {
  it("exposes the value on a progressbar role", () => {
    render(<ProgressBar label="Resume" value={62} />);
    const bar = screen.getByRole("progressbar", { name: "Resume" });
    expect(bar).toHaveAttribute("aria-valuenow", "62");
    expect(bar).toHaveAttribute("aria-valuemin", "0");
    expect(bar).toHaveAttribute("aria-valuemax", "100");
  });

  it("clamps a backend that reports more than 100%", () => {
    render(<ProgressBar label="Resume" value={140} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
  });

  it("clamps a negative value rather than rendering a backwards bar", () => {
    render(<ProgressBar label="Resume" value={-20} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");
  });

  it("rounds fractional progress", () => {
    render(<ProgressBar label="Resume" value={62.6} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "63");
  });

  it("can hide the numeric readout without losing it for screen readers", () => {
    render(<ProgressBar label="Resume" value={62} showValue={false} />);
    expect(screen.queryByText("62%")).not.toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "62");
  });
});

describe("StatCard", () => {
  it("shows a trend direction as a glyph as well as a colour", () => {
    render(<StatCard label="Applications" value={14} trend={{ direction: "up", label: "+3 this week" }} />);
    // Colour alone would leave the direction unreadable in greyscale or to a
    // colour-blind reader.
    expect(screen.getByText(/\+3 this week/)).toHaveTextContent("↑");
  });

  it("falls back to the hint when there is no trend", () => {
    render(<StatCard label="Applications" value={14} hint="Since January" />);
    expect(screen.getByText("Since January")).toBeInTheDocument();
  });

  it("hides its decorative icon from assistive technology", () => {
    const { container } = render(<StatCard label="Applications" value={14} icon="📝" />);
    expect(container.querySelector("[aria-hidden='true']")).toHaveTextContent("📝");
  });
});

interface Row {
  id: string;
  name: string;
  score: number;
}

const ROWS: Row[] = [
  { id: "1", name: "Taylor Reed", score: 9 },
  { id: "2", name: "Jordan Blake", score: 7 },
];

const COLUMNS: Column<Row>[] = [
  { key: "name", header: "Name", cell: (row) => row.name },
  { key: "score", header: "Score", cell: (row) => row.score, numeric: true },
  { key: "extra", header: "Extra", cell: () => "—", hideOnMobile: true },
];

describe("DataTable", () => {
  it("names the table for screen readers without showing a visible caption", () => {
    render(
      <DataTable rows={ROWS} columns={COLUMNS} rowKey={(r) => r.id} caption="Candidates" empty={{ title: "None" }} />,
    );
    expect(screen.getByRole("table", { name: "Candidates" })).toBeInTheDocument();
  });

  it("marks every header as a column header", () => {
    render(
      <DataTable rows={ROWS} columns={COLUMNS} rowKey={(r) => r.id} caption="Candidates" empty={{ title: "None" }} />,
    );
    expect(screen.getAllByRole("columnheader")).toHaveLength(3);
  });

  it("renders an empty state instead of a header with nothing under it", () => {
    render(
      <DataTable
        rows={[]}
        columns={COLUMNS}
        rowKey={(r) => r.id}
        caption="Candidates"
        empty={{ title: "No candidates yet", description: "They will appear once someone applies." }}
      />,
    );
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getByText("No candidates yet")).toBeInTheDocument();
    expect(screen.getByText("They will appear once someone applies.")).toBeInTheDocument();
  });

  it("renders cell content as text, so user-supplied values cannot inject markup", () => {
    const hostile: Row[] = [{ id: "1", name: "<img src=x onerror=alert(1)>", score: 1 }];
    render(
      <DataTable rows={hostile} columns={COLUMNS} rowKey={(r) => r.id} caption="Candidates" empty={{ title: "None" }} />,
    );
    expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeInTheDocument();
    expect(document.querySelector("img")).toBeNull();
  });
});

describe("states", () => {
  it("announces a spinner rather than leaving the page silent", () => {
    render(<Spinner label="Loading applications" />);
    // A live region is announced by its *contents*, not its accessible name,
    // so the label has to be text inside it rather than an aria-label.
    expect(screen.getByRole("status")).toHaveTextContent("Loading applications");
  });

  it("keeps skeleton bars out of the accessibility tree", () => {
    const { container } = render(<LoadingState label="Loading" rows={3} />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
    // One hidden wrapper holds every bar, so a screen reader hears the label
    // once rather than three empty rows after it.
    expect(container.querySelectorAll("[aria-hidden='true']")).toHaveLength(2);
  });

  it("renders an empty state's action so the screen offers a way forward", () => {
    render(<EmptyState title="No resumes" description="Upload one to begin." action={<button type="button">Upload</button>} />);
    expect(screen.getByRole("button", { name: "Upload" })).toBeInTheDocument();
  });
});
