import { describe, expect, it } from "vitest";

// `?raw` rather than `node:fs`: the app tsconfig deliberately does not pull in
// Node's types, and Vite resolves this the same way in the test run as it
// would in a build.
import theme from "@/styles/theme.css?raw";
import { cn } from "@/lib/cn";

describe("cn", () => {
  it("lets a later utility win over an earlier one in the same group", () => {
    expect(cn("px-4", "px-2")).toBe("px-2");
    expect(cn("rounded-md", "rounded-lg")).toBe("rounded-lg");
  });

  it("keeps utilities that do not conflict", () => {
    expect(cn("rounded-lg", "border")).toBe("rounded-lg border");
  });

  it("drops falsy values, which is how conditional classes are written", () => {
    const hidden = false;
    expect(cn("p-4", hidden && "hidden", undefined, null)).toBe("p-4");
  });

  /**
   * The regression this file mainly exists for. `tailwind-merge` classifies a
   * `text-*` class by its value, so a scale named by role rather than by size
   * lands in the colour group — and a font size next to a colour was being
   * silently dropped. It renders as body text with no error anywhere.
   */
  it("keeps a font size and a text colour together", () => {
    expect(cn("text-card-title", "text-ink")).toBe("text-card-title text-ink");
    expect(cn("text-display", "text-white")).toBe("text-display text-white");
    expect(cn("text-caption", "text-danger")).toBe("text-caption text-danger");
  });

  it("still treats two font sizes as a conflict", () => {
    expect(cn("text-body", "text-card-title")).toBe("text-card-title");
  });

  it("still treats two text colours as a conflict", () => {
    expect(cn("text-ink", "text-ink-soft")).toBe("text-ink-soft");
  });

  it("knows every font size the theme declares", () => {
    // If someone adds a `--text-*` token without listing it in `cn.ts`, that
    // size starts disappearing wherever it meets a colour. Catch it here.
    const declared = [...theme.matchAll(/^\s*--text-([\w-]+):\s/gm)]
      .map((m) => m[1] as string)
      // `--text-body--line-height` and friends are modifiers, not sizes.
      .filter((name) => !name.includes("--"));

    for (const size of new Set(declared)) {
      expect(cn(`text-${size}`, "text-ink"), `text-${size} was dropped`).toContain(`text-${size}`);
    }
  });
});
