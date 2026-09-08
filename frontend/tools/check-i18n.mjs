#!/usr/bin/env node
/**
 * i18n validation for the frontend lane (plan 08 §10).
 *
 * With one locale this still earns its place: it is the check that catches a
 * key added to the code and never added to the catalogue, an empty string
 * shipped as a translation, and — the moment a second locale exists — a
 * catalogue that drifted out of sync with the reference one.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const LOCALES_DIR = join(ROOT, "src", "i18n", "locales");
const REFERENCE_LOCALE = "en";
const SOURCE_DIR = join(ROOT, "src");

const problems = [];

function listFiles(dir, predicate) {
  const found = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      found.push(...listFiles(full, predicate));
    } else if (predicate(entry)) {
      found.push(full);
    }
  }
  return found;
}

function loadCatalogue(locale) {
  const namespaces = {};
  for (const file of listFiles(join(LOCALES_DIR, locale), (name) =>
    name.endsWith(".json"),
  )) {
    const namespace = relative(join(LOCALES_DIR, locale), file).replace(/\.json$/, "");
    namespaces[namespace] = JSON.parse(readFileSync(file, "utf8"));
  }
  return namespaces;
}

const locales = readdirSync(LOCALES_DIR).filter((entry) =>
  statSync(join(LOCALES_DIR, entry)).isDirectory(),
);

if (!locales.includes(REFERENCE_LOCALE)) {
  problems.push(`Reference locale "${REFERENCE_LOCALE}" is missing from ${LOCALES_DIR}`);
}

const catalogues = Object.fromEntries(
  locales.map((locale) => [locale, loadCatalogue(locale)]),
);
const reference = catalogues[REFERENCE_LOCALE] ?? {};

// 1. Every locale carries exactly the reference key set.
for (const [locale, catalogue] of Object.entries(catalogues)) {
  if (locale === REFERENCE_LOCALE) continue;
  for (const [namespace, entries] of Object.entries(reference)) {
    const theirs = catalogue[namespace] ?? {};
    for (const key of Object.keys(entries)) {
      if (!(key in theirs)) problems.push(`${locale}/${namespace}: missing key "${key}"`);
    }
    for (const key of Object.keys(theirs)) {
      if (!(key in entries)) problems.push(`${locale}/${namespace}: unknown key "${key}"`);
    }
  }
}

// 2. No empty value anywhere: an empty string renders as a blank label.
for (const [locale, catalogue] of Object.entries(catalogues)) {
  for (const [namespace, entries] of Object.entries(catalogue)) {
    for (const [key, value] of Object.entries(entries)) {
      if (typeof value !== "string" || value.trim() === "") {
        problems.push(`${locale}/${namespace}: key "${key}" has an empty value`);
      }
    }
  }
}

// 3. Every literal key passed to t("…") exists in the reference catalogue.
const T_CALL = /\bt\(\s*["'`]([^"'`]+)["'`]/g;
const declared = new Set(
  Object.entries(reference).flatMap(([namespace, entries]) =>
    Object.keys(entries).flatMap((key) => [key, `${namespace}:${key}`]),
  ),
);

for (const file of listFiles(SOURCE_DIR, (name) => /\.tsx?$/.test(name))) {
  if (file.endsWith(".test.ts") || file.endsWith(".test.tsx")) continue;
  const source = readFileSync(file, "utf8");
  for (const match of source.matchAll(T_CALL)) {
    const key = match[1];
    if (!declared.has(key)) {
      problems.push(`${relative(ROOT, file)}: t("${key}") is not in the ${REFERENCE_LOCALE} catalogue`);
    }
  }
}

if (problems.length > 0) {
  console.error("i18n check failed:");
  for (const problem of problems) console.error(`  - ${problem}`);
  process.exit(1);
}

console.log(
  `i18n check passed: ${locales.length} locale(s), ${declared.size / 2} key(s).`,
);
