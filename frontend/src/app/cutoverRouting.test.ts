import { matchRoutes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { routes } from "@/app/router";
// `?raw` rather than `node:fs`: the app's tsconfig deliberately carries no Node
// types (`types: ["vite/client", …]`), and adding them so one test can read a
// file would widen what every other file in `src` is allowed to reach for.
import NGINX_CONF from "../../nginx.conf?raw";

/**
 * Keeps `nginx.conf` and the route table honest about each other
 * (TASK-058 pre-flight, runbook §9).
 *
 * The cutover moved seven legacy URLs to a 301 and five legacy assets to a
 * redirect into the bundle. Every one of those targets is written in
 * `nginx.conf` and resolved by something in this repository — but the two live
 * in different files and different languages, so nothing stops someone from
 * renaming `/company/applicants` in the router and leaving the proxy pointing
 * at an address that no longer exists.
 *
 * The failure that would cause is quiet, which is what makes it worth a test:
 * the redirect still returns 301, the browser still follows it, and the person
 * lands on the not-found screen having been sent there by our own config.
 */
/**
 * Both capture groups of every match, dropping any match that somehow lacks
 * one. `noUncheckedIndexedAccess` types a capture group as possibly undefined,
 * and narrowing it here keeps that honesty out of the four call sites.
 */
function pairsFrom(matches: IterableIterator<RegExpExecArray>): [string, string][] {
  const pairs: [string, string][] = [];
  for (const [, from, to] of matches) {
    if (from !== undefined && to !== undefined) pairs.push([from, to]);
  }
  return pairs;
}

/**
 * `location = /user-profile { return 301 /profile; }`, and the one that is not
 * shaped like that: `/api/v1/auth/register` wraps its `return` in an
 * `if ($request_method ...)` so the POST still reaches the API. Matching only
 * the one-liner form silently skipped it — which is what the count assertion
 * below exists to catch.
 */
function screenRedirects(): [string, string][] {
  const pattern = /location\s+=\s+(\S+)\s*\{[^}]*?return\s+301\s+(\S+?);/g;
  return pairsFrom(NGINX_CONF.matchAll(pattern));
}

/** The `map $uri $legacy_asset_target` entries. */
function assetRedirects(): [string, string][] {
  const body = NGINX_CONF.match(/map \$uri \$legacy_asset_target \{([\s\S]*?)\n\}/)?.[1];
  if (!body) return [];
  return pairsFrom(body.matchAll(/^\s*(\/\S+)\s+(\/\S+?);/gm));
}

/**
 * Everything under `public/`, which Vite copies to the bundle root, keyed by
 * the path the browser asks for. `import.meta.glob` resolves at transform
 * time, so this is a real directory listing without a filesystem API.
 */
const BUNDLE_ROOT_FILES = new Set(
  Object.keys(import.meta.glob("../../public/**/*")).map((path) =>
    path.replace("../../public", ""),
  ),
);

/** Does the SPA have a real screen at this path, or only the catch-all? */
function resolvesToAScreen(path: string): boolean {
  const matches = matchRoutes(routes, path);
  const leaf = matches?.at(-1);
  if (!leaf) return false;
  return leaf.route.path !== "*";
}

describe("cutover redirects", () => {
  it("finds the redirects it is meant to be checking", () => {
    // Guards the parsing itself: a regex that silently matches nothing would
    // make every assertion below vacuously true.
    expect(screenRedirects().length).toBeGreaterThanOrEqual(7);
    expect(assetRedirects().length).toBeGreaterThanOrEqual(5);
  });

  it.each(screenRedirects())("%s redirects to %s, which is a real route", (_from, to) => {
    expect(resolvesToAScreen(to)).toBe(true);
  });

  it.each(assetRedirects())("%s redirects to %s, which is a file in the bundle", (_from, to) => {
    expect(BUNDLE_ROOT_FILES).toContain(to);
  });

  it("serves robots.txt and sitemap.xml instead of forwarding them", () => {
    // Runbook §7 option A. While these were in the proxy regex, the retire
    // matrix claimed the frontend owned them and the backend actually did —
    // so retiring them from FastAPI would have broken both.
    expect(NGINX_CONF).toMatch(/location = \/robots\.txt \{/);
    expect(NGINX_CONF).toMatch(/location = \/sitemap\.xml \{/);
    const proxyRegex = NGINX_CONF.match(/location ~ \^\/\(api\/[^)]*\)/)?.[0] ?? "";
    expect(proxyRegex).not.toContain("robots");
    expect(proxyRegex).not.toContain("sitemap");
    expect(BUNDLE_ROOT_FILES).toContain("/robots.txt");
    expect(BUNDLE_ROOT_FILES).toContain("/sitemap.xml");
  });

  it("still forwards the legacy auth mount, so the window can measure it", () => {
    // Runbook §4 B4: dropping it from the proxy would zero its traffic counter
    // by construction, and TASK-059 needs that counter to mean something.
    const proxyRegex = NGINX_CONF.match(/location ~ \^\/\(api\/[^)]*\)/)?.[0] ?? "";
    expect(proxyRegex).toContain("auth/jwt/");
  });
});

/**
 * The `map $uri $spa_route_known` block, as regexes. Nginx writes a regex entry
 * with a leading `~`; the rest is PCRE and survives being read by JavaScript's
 * engine unchanged, because these patterns use nothing the two spell
 * differently.
 */
function knownRoutePatterns(): RegExp[] {
  const body = NGINX_CONF.match(/map \$uri \$spa_route_known \{([\s\S]*?)\n\}/)?.[1];
  if (!body) return [];
  const patterns: RegExp[] = [];
  for (const [, source] of body.matchAll(/^\s*~(\S+)\s+1;/gm)) {
    if (source !== undefined) patterns.push(new RegExp(source));
  }
  return patterns;
}

function nginxWouldServe(path: string): boolean {
  return knownRoutePatterns().some((pattern) => pattern.test(path));
}

/** Every path in the route table, with `:params` filled in with a sample. */
function everyRoutePath(): string[] {
  const paths: string[] = [];
  const walk = (nodes: typeof routes): void => {
    for (const node of nodes) {
      if (node.path !== undefined && node.path !== "*") paths.push(node.path);
      if (node.children) walk(node.children as typeof routes);
    }
  };
  walk(routes);
  return paths.map((path) => path.replace(/:[^/]+/g, "sample-id"));
}

describe("the not-found status", () => {
  /**
   * Runbook §4 B1 and its acceptance item "una URL inexistente responde 404, no
   * 200". The history fallback cannot tell a screen from a typo on its own, so
   * nginx carries the route table and these tests are what keep the copy true.
   *
   * The dangerous direction is one-sided. A path missing from the map 404s a
   * real screen in production — silently, because the SPA still renders it.
   * A stale extra entry only costs a soft 404 on a route that no longer exists.
   * So the first test is the one that matters, and it runs over the router
   * rather than over a list written by hand.
   */
  it("finds the route map it is meant to be checking", () => {
    expect(knownRoutePatterns().length).toBeGreaterThanOrEqual(20);
  });

  it.each(everyRoutePath())("nginx knows %s is a real screen", (path) => {
    expect(nginxWouldServe(path)).toBe(true);
  });

  it.each([
    "/no-existe-esta-pagina",
    "/dashboardd",
    "/company/nope",
    "/jobs/applications/extra",
    "/user-profile",
  ])("nginx does not mistake %s for a screen", (path) => {
    expect(nginxWouldServe(path)).toBe(false);
  });

  it("answers an unknown path with 404 carrying the entry document", () => {
    // Both halves matter: `return 404` alone would send nginx's own page and
    // lose the not-found screen, and `error_page` alone would never fire.
    const fallback = NGINX_CONF.match(/location @spa \{([\s\S]*?)\n {4}\}/)?.[1] ?? "";
    expect(fallback).toContain("error_page 404 /index.html;");
    expect(fallback).toMatch(/if \(\$spa_route_known = 0\) \{\s*return 404;/);
    // And the history fallback has to reach it, or none of the above runs.
    expect(NGINX_CONF).toMatch(/try_files \$uri \$uri\/ @spa;/);
  });

  it("does not turn the scanner 404s into the entry document", () => {
    // error_page at server level would catch the extension rule too, and every
    // probe for /.env would come back looking like the application.
    const serverLevel = NGINX_CONF.replace(/location @spa \{[\s\S]*?\n {4}\}/, "");
    expect(serverLevel).not.toContain("error_page 404");
  });
});
