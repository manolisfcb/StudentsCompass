import { ICON_ART } from "@/components/ui/icons.generated";

export type { IconName, IconVariant } from "@/components/ui/icons.generated";

import type { IconName } from "@/components/ui/icons.generated";

/**
 * Every glyph in the product is an Iconsax icon, and every one of them is
 * named here or in the registry `tools/build-icons.mjs` generates this from.
 *
 * The screens used to draw emoji — 📊, 🎯, 🎉 — which cost nothing to write
 * and read as a placeholder: an emoji is a font, so it renders in the host
 * platform's own style (one shape on a Mac, another on Windows, a third on
 * Android), it cannot take `currentColor`, and it never matches the weight of
 * the text beside it. These are paths at a single stroke weight that inherit
 * the colour of whatever they sit in.
 */

/**
 * Iconsax has no bare ✕ — the close glyph only ships inside a circle or a
 * square. A plus turned a quarter-turn is the same two strokes at the same
 * weight, which is how the set draws it anyway.
 */
export const ROTATED: Partial<Record<IconName, string>> = {
  close: "rotate-45",
};

/**
 * The emoji the API still stores.
 *
 * `resources.icon` and `communities.icon` are free-text columns seeded with
 * emoji, and rows created before this change keep theirs. Rather than migrate
 * the data — and rather than let one stray 🐍 undo the set on a page — the
 * stored value is resolved here: an icon name is used as-is, a known emoji is
 * translated, and anything else falls back to the caller's default.
 */
const FROM_EMOJI: Record<string, IconName> = {
  "🎓": "graduation",
  "🎤": "mic",
  "🎙": "mic",
  "🎨": "design",
  "🎯": "target",
  "🎉": "trophy",
  "🏆": "trophy",
  "🏗": "briefcase",
  "🏢": "building",
  "🐍": "code",
  "👤": "user",
  "👥": "users",
  "💎": "gem",
  "💡": "idea",
  "💬": "message",
  "💰": "money",
  "💼": "briefcase",
  "💻": "monitor",
  "📄": "document",
  "📈": "trend-up",
  "📉": "trend-down",
  "📊": "chart",
  "📋": "clipboard",
  "📑": "clipboard",
  "📖": "book",
  "📚": "book",
  "📝": "note",
  "📬": "inbox",
  "🔍": "search",
  "🔒": "lock",
  "🕵": "search",
  "🗄": "database",
  "🗣": "mic",
  "🛠": "settings",
  "🛡": "shield",
  "🤝": "people",
  "🧠": "idea",
  "🧩": "category",
  "🧭": "compass",
  "⚡": "flash",
  "⭐": "star",
  "✅": "check-circle",
};

export function toIconName(value: string | null | undefined, fallback: IconName): IconName {
  if (!value) return fallback;
  // U+FE0F is the "render this as an emoji" selector; 🗄️ and 🗄 are the same
  // character to a reader and two different keys to a lookup table.
  const key = value.trim().replace(/️/g, "");
  if (key in ICON_ART) return key as IconName;
  return FROM_EMOJI[key] ?? fallback;
}
