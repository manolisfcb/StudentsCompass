import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import { AboutPage } from "@/features/marketing/AboutPage";

describe("AboutPage", () => {
  it("renders the hero", () => {
    render(
      <MemoryRouter>
        <AboutPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "We Don't Sell Jobs.We Deliver Job-Ready Talent.",
    );
  });

  it("opens a stat's citation in a dialog and closes it on Escape", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AboutPage />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: /49%/ }));

    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("49% — Lack of Relevant Experience in Entry-Level Hiring");
    expect(screen.getByRole("link", { name: "View Original Source ↗" })).toHaveAttribute(
      "href",
      "https://www.expresspros.ca/newsroom/news-releases/news-releases/2025/02/canadian-companies-say-worsening-skills-gap-and-navigating-ai-top-challenges-in-2025",
    );

    await user.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows the additional source link only for the stat that has one", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AboutPage />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: /\$30,680/ }));

    expect(screen.getByRole("link", { name: "View additional source (Robert Half) ↗" })).toBeInTheDocument();
  });
});
