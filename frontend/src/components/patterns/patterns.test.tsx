import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";
import { AsyncBoundary, QueryError } from "@/components/patterns/AsyncBoundary";
import { DataTable } from "@/components/patterns/DataTable";
import { EmptyState } from "@/components/patterns/EmptyState";
import "@/i18n";

function withClient(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function Probe({ queryFn }: { queryFn: () => Promise<string> }) {
  const query = useQuery({ queryKey: ["probe", queryFn], queryFn, retry: false });
  return <AsyncBoundary query={query}>{(value) => <p>{value}</p>}</AsyncBoundary>;
}

describe("AsyncBoundary", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("announces loading to assistive technology rather than rendering nothing", () => {
    render(withClient(<Probe queryFn={() => new Promise<string>(() => {})} />));
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("renders children only once the value has settled", async () => {
    render(withClient(<Probe queryFn={() => Promise.resolve("settled")} />));
    expect(await screen.findByText("settled")).toBeInTheDocument();
  });

  it("renders the error state instead of the children on failure", async () => {
    render(withClient(<Probe queryFn={() => Promise.reject(new Error("nope"))} />));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});

describe("QueryError", () => {
  it("shows the API's own message and the request id that finds it in the logs", () => {
    const error = new ApiError(429, "429 /api/v1/x", {
      body: {
        error: {
          code: "rate_limited",
          message: "Too many requests.",
          request_id: "req-42",
        },
      },
    });

    render(<QueryError error={error} />);

    expect(screen.getByText("Too many requests.")).toBeInTheDocument();
    expect(screen.getByText(/req-42/)).toBeInTheDocument();
  });

  it("does not leak the message of a non-API error", () => {
    render(<QueryError error={new Error("connection string: postgres://secret")} />);

    expect(screen.queryByText(/postgres:\/\/secret/)).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("offers a retry that calls back", async () => {
    const onRetry = vi.fn();
    render(<QueryError error={new Error("x")} onRetry={onRetry} />);

    await userEvent.click(screen.getByRole("button"));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});

describe("DataTable", () => {
  interface Row {
    id: string;
    name: string;
    count: number;
  }

  const columns = [
    { key: "name", header: "Name", cell: (row: Row) => row.name },
    { key: "count", header: "Count", cell: (row: Row) => row.count, numeric: true },
  ];

  it("renders an empty state instead of a bare header when there are no rows", () => {
    render(
      <DataTable
        rows={[]}
        columns={columns}
        rowKey={(row) => row.id}
        empty={{ title: "Nothing yet" }}
        caption="rows"
      />,
    );

    expect(screen.getByText("Nothing yet")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("renders user-supplied text as text, which is the lesson of F-03", () => {
    render(
      <DataTable
        rows={[{ id: "1", name: "<img src=x onerror=alert(1)>", count: 2 }]}
        columns={columns}
        rowKey={(row) => row.id}
        empty={{ title: "Nothing yet" }}
        caption="rows"
      />,
    );

    expect(screen.getByRole("cell", { name: "<img src=x onerror=alert(1)>" })).toBeInTheDocument();
    expect(document.querySelector("img")).toBeNull();
  });
});

describe("EmptyState", () => {
  it("renders an optional action", () => {
    render(<EmptyState title="None" description="yet" action={<button>Add</button>} />);
    expect(screen.getByRole("button", { name: "Add" })).toBeInTheDocument();
  });
});
