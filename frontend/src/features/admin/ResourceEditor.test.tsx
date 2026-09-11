import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ResourceEditor } from "@/features/admin/ResourceEditor";
import "@/i18n";

describe("ResourceEditor", () => {
  it("builds modules and lessons into the generated resource contract", async () => {
    const onSave = vi.fn<(payload: unknown) => Promise<void>>(() => Promise.resolve());
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={client}>
        <ResourceEditor onSave={onSave} onCancel={vi.fn()} />
      </QueryClientProvider>,
    );

    await user.type(screen.getByLabelText("Title"), "Interview Prep");
    await user.type(screen.getByLabelText("Category"), "career");
    await user.type(screen.getByLabelText("Description"), "Practice concise stories.");
    await user.click(screen.getByRole("button", { name: "Add Module" }));
    await user.type(screen.getByLabelText("Module title"), "STAR method");
    await user.type(screen.getByLabelText("Lesson title"), "Build a story");
    await user.type(screen.getByLabelText("Lesson content"), "Situation, task, action, result.");
    await user.click(screen.getByRole("button", { name: "Save Resource" }));

    await waitFor(() => expect(onSave).toHaveBeenCalledOnce());
    expect(onSave.mock.calls[0]?.[0]).toMatchObject({
      title: "Interview Prep",
      category: "career",
      is_published: true,
      is_locked: false,
      modules: [{ title: "STAR method", lessons: [{ title: "Build a story", content_type: "text" }] }],
    });
  });
});
