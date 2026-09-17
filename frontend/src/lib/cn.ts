import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

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
