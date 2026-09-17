/**
 * Contrast gate for the design tokens.
 *
 * Reads `src/styles/theme.css` and checks every foreground/background pair the
 * design system actually puts together — in both the light theme and the dark
 * admin scope — against the WCAG 2.1 AA thresholds.
 *
 * This exists because "improve colour contrast" is not a thing you do once.
 * A token file is small enough that every combination can be enumerated, so
 * the next person to nudge a colour finds out here rather than in an audit.
 *
 *   node tools/check-contrast.mjs
 *
 * Exits non-zero on a failure, so it can gate CI.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const THEME = readFileSync(fileURLToPath(new URL("../src/styles/theme.css", import.meta.url)), "utf8");

/** Pulls the `--color-*` declarations out of one block of the theme file. */
function readTokens(source) {
  const tokens = new Map();
  for (const m of source.matchAll(/(--color-[\w-]+)\s*:\s*([^;]+);/g)) {
    tokens.set(m[1], m[2].trim());
  }
  return tokens;
}

// Sliced on the rule openers, not on a bare name — the file's header comment
// mentions `.theme-dark` long before the rule itself.
const darkAt = THEME.indexOf(".theme-dark {");
const bridgeAt = THEME.indexOf(":root {");
const lightBlock = THEME.slice(THEME.indexOf("@theme {"), darkAt);
const darkBlock = THEME.slice(darkAt, bridgeAt);

const LIGHT = readTokens(lightBlock);
const DARK = new Map([...LIGHT, ...readTokens(darkBlock)]);

/** #rrggbb, or rgba(...) composited over a given backdrop. */
function toRgb(value, backdrop) {
  const hex = value.match(/^#([0-9a-f]{6})$/i);
  if (hex) {
    const n = parseInt(hex[1], 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  const rgba = value.match(/rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,/\s]+([\d.]+))?\s*\)/);
  if (rgba) {
    const [r, g, b] = [Number(rgba[1]), Number(rgba[2]), Number(rgba[3])];
    const a = rgba[4] === undefined ? 1 : Number(rgba[4]);
    if (a === 1 || !backdrop) return [r, g, b];
    // A translucent token only has a real colour once it is over something.
    return [0, 1, 2].map((i) => Math.round(a * [r, g, b][i] + (1 - a) * backdrop[i]));
  }
  throw new Error(`Cannot parse colour: ${value}`);
}

function luminance([r, g, b]) {
  const [R, G, B] = [r, g, b].map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * R + 0.7152 * G + 0.0722 * B;
}

function ratio(fg, bg) {
  const [a, b] = [luminance(fg), luminance(bg)].sort((x, y) => y - x);
  return (a + 0.05) / (b + 0.05);
}

/**
 * The pairs the components actually render. `min` is the WCAG AA threshold
 * that applies: 4.5 for body text, 3.0 for large text (>=18.66px bold or
 * >=24px) and for the boundary of a UI component.
 */
const PAIRS = [
  // Text on the three surfaces.
  ["--color-ink", "--color-surface", 4.5, "body text on a card"],
  ["--color-ink", "--color-canvas", 4.5, "body text on the page"],
  ["--color-ink", "--color-surface-subtle", 4.5, "body text on a sunken panel"],
  ["--color-ink-soft", "--color-surface", 4.5, "secondary text on a card"],
  ["--color-ink-soft", "--color-canvas", 4.5, "secondary text on the page"],
  ["--color-ink-soft", "--color-surface-subtle", 4.5, "secondary text on a sunken panel"],
  // `ink-muted` is only ever used for non-essential text — captions, hints,
  // counts — so it is held to the large-text threshold rather than 4.5.
  ["--color-ink-muted", "--color-surface", 3.0, "muted caption on a card"],
  ["--color-ink-muted", "--color-canvas", 3.0, "muted caption on the page"],
  ["--color-ink-muted", "--color-surface-subtle", 3.0, "muted caption on a sunken panel"],

  // Primary action.
  ["--color-primary-fg", "--color-primary", 4.5, "primary button label"],
  ["--color-primary-fg", "--color-primary-hover", 4.5, "primary button label, hovered"],
  ["--color-primary-fg", "--color-primary-active", 4.5, "primary button label, pressed"],
  ["--color-primary", "--color-surface", 4.5, "link on a card"],
  ["--color-primary", "--color-canvas", 4.5, "link on the page"],
  ["--color-primary", "--color-primary-subtle", 4.5, "secondary button label"],
  ["--color-primary", "--color-primary-muted", 4.5, "secondary button label, hovered"],

  // Status text on its own tint — badges and alerts.
  ["--color-success", "--color-success-subtle", 4.5, "success badge"],
  ["--color-warning", "--color-warning-subtle", 4.5, "warning badge"],
  ["--color-danger", "--color-danger-subtle", 4.5, "danger badge"],
  ["--color-info", "--color-info-subtle", 4.5, "info badge"],
  ["--color-success", "--color-surface", 4.5, "success text on a card"],
  ["--color-warning", "--color-surface", 4.5, "warning text on a card"],
  ["--color-danger", "--color-surface", 4.5, "danger text on a card"],
  ["--color-info", "--color-surface", 4.5, "info text on a card"],

  // Destructive action.
  ["--color-danger-fg", "--color-danger", 4.5, "danger button label"],
  ["--color-danger-fg", "--color-danger-hover", 4.5, "danger button label, hovered"],

  // Component boundaries: a control has to be findable, not just readable.
  ["--color-border-strong", "--color-surface", 3.0, "input border on a card"],
  ["--color-primary", "--color-surface", 3.0, "focus ring on a card"],
  ["--color-primary", "--color-canvas", 3.0, "focus ring on the page"],
];

let failures = 0;
let checks = 0;

for (const [themeName, tokens] of [
  ["light", LIGHT],
  ["dark (admin)", DARK],
]) {
  console.log(`\n${themeName}`);
  const canvas = toRgb(tokens.get("--color-canvas"));

  for (const [fgToken, bgToken, min, what] of PAIRS) {
    const fgRaw = tokens.get(fgToken);
    const bgRaw = tokens.get(bgToken);
    if (!fgRaw || !bgRaw) {
      console.error(`  ✗ unknown token in pair ${fgToken} / ${bgToken}`);
      failures++;
      continue;
    }
    // Translucent tints are composited over the canvas they sit on.
    const bg = toRgb(bgRaw, canvas);
    const fg = toRgb(fgRaw, bg);
    const value = ratio(fg, bg);
    checks++;

    const ok = value >= min;
    if (!ok) failures++;
    const mark = ok ? "✓" : "✗";
    const line = `  ${mark} ${value.toFixed(2)}:1 (min ${min.toFixed(1)}) — ${what}`;
    if (ok) console.log(line);
    else console.error(`${line}   [${fgToken} on ${bgToken}]`);
  }
}

console.log(`\n${checks} pairs checked, ${failures} below threshold.`);
process.exit(failures > 0 ? 1 : 0);
