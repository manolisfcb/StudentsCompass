import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import { HomePage } from "@/features/marketing/HomePage";

describe("HomePage", () => {
  it("renders the hero and links to registration", () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "From confused student to job-ready candidate, with one clear system.",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Get Started for Free" })).toHaveAttribute("href", "/register");
    expect(screen.getByRole("link", { name: "See how it works" })).toHaveAttribute("href", "/about");
  });

  it("sets the document title from the home SEO metadata", () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(document.title).toBe("Students Compass | Career Platform in Canada");
  });
});
