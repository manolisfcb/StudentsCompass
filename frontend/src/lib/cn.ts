import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/**
 * The design system's type scale, by name.
 *
 * `tailwind-merge` has to be told about these. Out of the box it decides what
 * a `text-*` class means by looking at the value: a t-shirt size or a length
 * is a font size, and anything else is a colour. Our scale is named by role,
 * so `text-card-title` was being filed as a colour — which put it in the same
 * conflict group as `text-ink`, and `cn("text-card-title", "text-ink")`
 * silently returned just `text-ink`. Every heading rendered at body size and
 * nothing anywhere reported an error.
 *
 * Kept in sync with the `--text-*` entries in `styles/theme.css`.
 */
const FONT_SIZES = [
  "display",
  "page-title",
  "section-title",
  "card-title",
  "body",
  "body-sm",
  "label",
  "caption",
  "overline",
] as const;

const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [{ text: [...FONT_SIZES] }],
    },
  },
});

/**
 * Join class names, letting the last conflicting utility win.
 *
 * `clsx` alone would keep both of `px-4` and `px-2` in the string and leave
 * the winner to stylesheet order, which is not something a caller can reason
 * about. `twMerge` drops the earlier one, so a component's defaults can be
 * overridden by the `className` a caller passes — the property every variant
 * component here depends on.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
