#!/usr/bin/env node
/**
 * Generates the app's icon artwork from Iconsax.
 *
 * `iconsax-reactjs` ships one module per icon carrying all six variants —
 * Linear, Outline, Broken, Bold, Bulk and TwoTone — behind a `switch` on a
 * prop. A bundler cannot drop the five we never render, because the switch
 * references them all, so importing fifty icons at runtime cost about 45 kB
 * gzipped of paths nothing on any screen draws.
 *
 * So the package is a build-time dependency: this script renders the two
 * variants the product actually uses and writes them out as data. Rerun it
 * (`npm run icons:build`) after adding a name to REGISTRY below or upgrading
 * the package; the output is committed, so a normal install and build never
 * needs Iconsax at all.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import * as Iconsax from "iconsax-reactjs";

/**
 * The semantic name each screen asks for, and the Iconsax icon that draws it.
 *
 * Names describe meaning, not the picture — `applications`, not `paper`. That
 * is what lets the drawing change without a search across the app, and what
 * stops one idea picking two different glyphs on two screens.
 */
const REGISTRY = {
  "arrow-down": "ArrowDown",
  "arrow-left": "ArrowLeft",
  "arrow-right": "ArrowRight",
  "arrow-up": "ArrowUp",
  book: "Book1",
  briefcase: "Briefcase",
  building: "Building",
  buildings: "Buildings2",
  category: "Category",
  chart: "Chart",
  check: "Check",
  "check-circle": "TickCircle",
  clipboard: "ClipboardText",
  close: "Add",
  "close-circle": "CloseCircle",
  code: "Code",
  compass: "Discover",
  danger: "Danger",
  database: "Data2",
  design: "ColorSwatch",
  document: "DocumentText",
  external: "ExportCurve",
  flash: "Flash",
  gem: "Diamonds",
  globe: "Global",
  graduation: "Teacher",
  idea: "LampOn",
  inbox: "DirectInbox",
  info: "InfoCircle",
  lock: "Lock",
  menu: "HamburgerMenu",
  message: "Message",
  messages: "Messages2",
  mic: "Microphone2",
  money: "Money",
  monitor: "Monitor",
  note: "Note",
  overview: "Element3",
  people: "People",
  presentation: "PresentionChart",
  route: "Routing",
  schedule: "CalendarTick",
  search: "SearchNormal1",
  settings: "Setting2",
  shield: "SecuritySafe",
  star: "Star",
  target: "Gps",
  "trend-down": "TrendDown",
  "trend-up": "TrendUp",
  trophy: "Cup",
  user: "User",
  users: "Profile2User",
};

const VARIANTS = ["Linear", "Bold"];

/**
 * Attributes every path of a variant carries. They are presentation
 * attributes, so they inherit — setting them once on the `<svg>` leaves each
 * path holding only its own outline plus whatever it does differently.
 */
const INHERITED = {
  Linear: {
    stroke: "currentColor",
    "stroke-width": "1.5",
    "stroke-linecap": "round",
    "stroke-linejoin": "round",
  },
  Bold: { fill: "currentColor" },
};

const camel = (name) => name.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());

function pathsOf(iconName, variant) {
  const Glyph = Iconsax[iconName];
  if (!Glyph) throw new Error(`iconsax-reactjs has no icon named "${iconName}"`);

  const markup = renderToStaticMarkup(createElement(Glyph, { variant, color: "currentColor" }));
  const elements = [...markup.matchAll(/<(\w+)\b([^>]*?)\/?>/g)].filter(([, tag]) => tag !== "svg");

  const unexpected = elements.find(([, tag]) => tag !== "path");
  if (unexpected) throw new Error(`${iconName}/${variant} draws a <${unexpected[1]}>, which this script cannot carry`);

  return elements.map(([, , attributes]) => {
    const props = {};
    for (const [, key, value] of attributes.matchAll(/([\w-]+)="([^"]*)"/g)) {
      if (INHERITED[variant][key] === value) continue;
      props[camel(key)] = value;
    }
    return props;
  });
}

const entries = Object.entries(REGISTRY).map(([name, iconName]) => {
  const variants = VARIANTS.map((variant) => {
    const paths = pathsOf(iconName, variant);
    if (paths.length === 0) throw new Error(`${iconName}/${variant} rendered nothing`);
    return `    ${variant}: [${paths.map((props) => JSON.stringify(props)).join(", ")}],`;
  });
  return `  "${name}": {\n${variants.join("\n")}\n  },`;
});

const { version } = JSON.parse(
  readFileSync(new URL("../node_modules/iconsax-reactjs/package.json", import.meta.url), "utf8"),
);

const output = `import type { SVGProps } from "react";

/**
 * GENERATED FILE — do not edit.
 *
 * Written by \`npm run icons:build\` from iconsax-reactjs@${version}. Add a
 * name to the registry in \`tools/build-icons.mjs\` and rerun it; editing a
 * path here is undone by the next run.
 *
 * Each entry holds the paths of one icon in the two variants the product
 * draws. What every path of a variant shares — stroke colour, weight, joins —
 * sits on the \`<svg>\` in \`Icon.tsx\` instead of being repeated here.
 */
export const ICON_ART = {
${entries.join("\n")}
} as const satisfies Record<string, Record<"Linear" | "Bold", readonly SVGProps<SVGPathElement>[]>>;

export type IconName = keyof typeof ICON_ART;
export type IconVariant = "Linear" | "Bold";
`;

const target = fileURLToPath(new URL("../src/components/ui/icons.generated.ts", import.meta.url));
writeFileSync(target, output);
console.log(`icons:build wrote ${Object.keys(REGISTRY).length} icons from iconsax-reactjs@${version}`);
