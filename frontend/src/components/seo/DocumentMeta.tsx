import { useEffect } from "react";

/**
 * Per-page SEO, preserved from the Jinja templates the SPA replaces
 * (TASK-046, plan 08 §13: "el sitemap y datos estructurados existen hoy y una
 * SPA los pierde si nadie se ocupa").
 *
 * `base.html` set title, description, canonical and Open Graph tags per
 * request because the server knew which page it was rendering. A client-side
 * route has the same information one render later, so this hook sets the same
 * tags imperatively on mount and restores whatever was there before on
 * unmount — the same reason `AsyncBoundary` does not own the document, only
 * one page owns it at a time and the previous one's values must not leak
 * across a client-side navigation.
 *
 * The two site-wide `application/ld+json` blocks (Organization, WebSite) do
 * not vary per page, so they live once in `index.html` instead of being
 * re-created here on every route.
 */

export const PUBLIC_BASE_URL = "https://studentscompass.ca";

function upsertMeta(attr: "name" | "property", key: string, content: string): () => void {
  const selector = `meta[${attr}="${key}"]`;
  const existing = document.head.querySelector<HTMLMetaElement>(selector);
  const previousContent = existing?.getAttribute("content") ?? null;
  const element = existing ?? document.createElement("meta");
  if (!existing) {
    element.setAttribute(attr, key);
    document.head.appendChild(element);
  }
  element.setAttribute("content", content);

  return () => {
    if (existing) {
      if (previousContent !== null) element.setAttribute("content", previousContent);
    } else {
      element.remove();
    }
  };
}

function upsertCanonical(href: string): () => void {
  const existing = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  const previousHref = existing?.getAttribute("href") ?? null;
  const element = existing ?? document.createElement("link");
  if (!existing) {
    element.setAttribute("rel", "canonical");
    document.head.appendChild(element);
  }
  element.setAttribute("href", href);

  return () => {
    if (existing) {
      if (previousHref !== null) element.setAttribute("href", previousHref);
    } else {
      element.remove();
    }
  };
}

function injectJsonLd(data: object): () => void {
  const script = document.createElement("script");
  script.type = "application/ld+json";
  script.textContent = JSON.stringify(data);
  document.head.appendChild(script);
  return () => script.remove();
}

export function DocumentMeta({
  title,
  description,
  path,
  jsonLd,
  noindex = false,
}: {
  /** Page title, without the "Students Compass | " prefix `base.html` added. */
  title: string;
  description: string;
  /** Path only; `PUBLIC_BASE_URL` is prepended, matching `base.html`'s `canonical_url`. */
  path: string;
  jsonLd?: object;
  /**
   * Emits `<meta name="robots" content="noindex">` while the page is mounted.
   *
   * This exists for the not-found screen. A client-rendered SPA cannot answer
   * an unknown URL with a real 404: by the time the router knows the route does
   * not exist, nginx has already sent `200` with the entry document. `noindex`
   * is how you tell a crawler that the 200 it just received is not a page —
   * without it, every retired URL and every scanner probe reads as a live page
   * that happens to say "not found" (runbook §4, B1).
   */
  noindex?: boolean;
}) {
  useEffect(() => {
    const previousTitle = document.title;
    const fullTitle = `Students Compass | ${title}`;
    document.title = fullTitle;
    const canonicalUrl = `${PUBLIC_BASE_URL}${path}`;

    const restores = [
      upsertMeta("name", "description", description),
      upsertCanonical(canonicalUrl),
      upsertMeta("property", "og:title", fullTitle),
      upsertMeta("property", "og:description", description),
      upsertMeta("property", "og:url", canonicalUrl),
      noindex ? upsertMeta("name", "robots", "noindex") : null,
      jsonLd ? injectJsonLd(jsonLd) : null,
    ];

    return () => {
      document.title = previousTitle;
      for (const restore of restores) restore?.();
    };
  }, [title, description, path, jsonLd, noindex]);

  return null;
}
