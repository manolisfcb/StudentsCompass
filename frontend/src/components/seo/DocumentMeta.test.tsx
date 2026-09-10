import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DocumentMeta } from "@/components/seo/DocumentMeta";

function description(): string | null {
  return document.head.querySelector('meta[name="description"]')?.getAttribute("content") ?? null;
}

function canonical(): string | null {
  return document.head.querySelector('link[rel="canonical"]')?.getAttribute("href") ?? null;
}

describe("DocumentMeta", () => {
  it("sets the title, description and canonical URL", () => {
    const { unmount } = render(
      <DocumentMeta title="Login" description="Access your account." path="/login" />,
    );

    expect(document.title).toBe("Students Compass | Login");
    expect(description()).toBe("Access your account.");
    expect(canonical()).toBe("https://studentscompass.ca/login");

    unmount();
  });

  it("restores the previous values on unmount instead of leaving a stale tag", () => {
    document.title = "Before";
    const meta = document.createElement("meta");
    meta.setAttribute("name", "description");
    meta.setAttribute("content", "Original description.");
    document.head.appendChild(meta);

    const { unmount } = render(
      <DocumentMeta title="About" description="New description." path="/about" />,
    );
    expect(description()).toBe("New description.");

    unmount();

    expect(document.title).toBe("Before");
    expect(description()).toBe("Original description.");
    meta.remove();
  });

  it("injects and removes a JSON-LD block", () => {
    const { unmount } = render(
      <DocumentMeta
        title="About"
        description="d"
        path="/about"
        jsonLd={{ "@context": "https://schema.org", "@type": "AboutPage" }}
      />,
    );

    const script = document.head.querySelector('script[type="application/ld+json"]');
    expect(script?.textContent).toContain("AboutPage");

    unmount();

    expect(document.head.querySelector('script[type="application/ld+json"]')).toBeNull();
  });
});
