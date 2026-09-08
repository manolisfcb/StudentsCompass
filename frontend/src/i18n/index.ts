import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./locales/en/common.json";

/**
 * i18n is wired from the first screen even though the product ships one
 * language today (`<html lang="en">`, no translated content anywhere in the 27
 * templates). The reason is cost asymmetry: adding the provider now costs one
 * file, whereas retrofitting `t()` across eight verticals later means touching
 * every screen again. Plan 08 §10 already lists an i18n validation step in the
 * frontend CI lane, so the pipeline assumes this exists.
 *
 * See docs/refactor/ADR-002-frontend-styling-and-i18n.md.
 */
export const DEFAULT_LOCALE = "en";
export const SUPPORTED_LOCALES = [DEFAULT_LOCALE] as const;
export const DEFAULT_NAMESPACE = "common";

void i18n.use(initReactI18next).init({
  resources: { en: { common: en } },
  lng: DEFAULT_LOCALE,
  fallbackLng: DEFAULT_LOCALE,
  defaultNS: DEFAULT_NAMESPACE,
  ns: [DEFAULT_NAMESPACE],
  interpolation: {
    // React escapes for us; double-escaping would render entities as text.
    escapeValue: false,
  },
  // A key that reaches the browser untranslated is a bug, not a fallback.
  // i18next only calls `missingKeyHandler` when `saveMissing` is on, so both
  // flags move together: loud in dev and in tests, silent in production.
  saveMissing: !import.meta.env.PROD,
  missingKeyHandler: (_lngs, ns, key) => {
    throw new Error(`Missing i18n key "${ns}:${key}"`);
  },
});

export default i18n;
