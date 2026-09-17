import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import { HomeHero } from "@/features/marketing/HomeHero";
import { HomePage } from "@/features/marketing/HomePage";

describe("HomePage", () => {
  it("renders the hero and links to registration", () => {
    // The hero renders inside the shell's header, the way `home.html` nests it
    // under `.marketing-header`; `PublicShell` is what pairs the two.
    render(
      <MemoryRouter>
        <HomeHero />
        <HomePage />
      </MemoryRouter>,
    );

    // Level 1, not the 2 the ported markup used. The shell's brand is a link
    // and an image now rather than a heading, so the hero title is the page's
    // only `h1` — which is where a document outline should start.
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "From confused student to job-ready candidate, with one clear system.",
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
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
