import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

/**
 * The marketing pages' shared furniture.
 *
 * Both pages are a stack of full-bleed bands, each holding a centred heading
 * and a grid of cards. The ported sheets expressed that with a class per band
 * (`.home-audience-section-students`, `.about-section-alt`, `.about-section--stats`…),
 * which is how two pages ended up with six paddings and four heading styles
 * for the same three shapes. These three components are that vocabulary.
 */

export type BandTone = "canvas" | "surface" | "tint" | "brand" | "dark";

const BANDS: Record<BandTone, string> = {
  canvas: "bg-canvas",
  surface: "bg-surface",
  // The soft teal wash the audience bands use to separate themselves from the
  // white sections above and below them.
  tint: "bg-gradient-to-b from-surface to-primary-subtle",
  brand: "bg-gradient-to-br from-primary to-primary-bright text-white",
  dark: "bg-gradient-to-br from-ink to-ink-deep text-white",
};

/** A full-bleed band with the page's standard vertical rhythm and gutter. */
export function Band({
  tone = "canvas",
  id,
  className,
  children,
}: {
  tone?: BandTone;
  id?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className={cn("px-4 py-16 sm:py-20", BANDS[tone], className)}>
      <div className="mx-auto max-w-content">{children}</div>
    </section>
  );
}

/**
 * A band's centred heading: eyebrow, title, and an optional line of intro.
 *
 * `onDark` only changes the colours. The sizes come from the type scale, so a
 * marketing heading and a product page title stay in the same family.
 */
export function SectionHead({
  kicker,
  title,
  intro,
  onDark = false,
  className,
}: {
  /** Optional: some bands carry their own badge above the heading instead. */
  kicker?: string;
  title: ReactNode;
  intro?: string;
  onDark?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("mx-auto mb-10 max-w-2xl text-center", className)}>
      {kicker ? (
        <span
          className={cn(
            "mb-4 inline-flex rounded-full px-3 py-1 text-overline uppercase",
            onDark ? "bg-white/10 text-primary-bright" : "bg-primary-subtle text-primary",
          )}
        >
          {kicker}
        </span>
      ) : null}
      <h2 className={cn("text-display text-balance", onDark ? "text-white" : "text-ink")}>{title}</h2>
      {intro ? (
        <p className={cn("mt-4 text-body", onDark ? "text-white/70" : "text-ink-soft")}>{intro}</p>
      ) : null}
    </div>
  );
}

/**
 * A card in a marketing grid.
 *
 * It is not the product `Card`: this one carries the accent rule along its
 * bottom edge that the landing pages use, and it lifts on hover because the
 * whole grid reads as a set of things to look at. Everything else — radius,
 * border, surface — is the same token scale, so the two families still look
 * like one product.
 */
export function MarketingCard({
  icon,
  title,
  body,
  onDark = false,
  className,
  children,
}: {
  icon?: ReactNode;
  title?: ReactNode;
  body?: string;
  onDark?: boolean;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <article
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-lg border p-6 transition-[transform,box-shadow,border-color] duration-200",
        onDark
          ? "border-white/10 bg-white/5 hover:border-white/20"
          : "border-border bg-surface shadow-xs hover:-translate-y-0.5 hover:border-border-strong hover:shadow-md",
        className,
      )}
    >
      {icon ? (
        <span
          aria-hidden="true"
          className={cn(
            "mb-4 flex size-11 items-center justify-center rounded-lg text-xl",
            onDark ? "bg-white/10" : "bg-primary-subtle",
          )}
        >
          {icon}
        </span>
      ) : null}

      {title ? (
        <h3 className={cn("text-card-title text-balance", onDark ? "text-white" : "text-ink")}>{title}</h3>
      ) : null}
      {body ? (
        <p className={cn("mt-2 text-body-sm", onDark ? "text-white/70" : "text-ink-soft")}>{body}</p>
      ) : null}

      {children}

      {/* The accent rule the ported cards drew with a `::after`. Decorative,
        * so it is not in the accessibility tree. */}
      {onDark ? null : (
        <span
          aria-hidden="true"
          className="absolute inset-x-0 bottom-0 h-0.5 bg-gradient-to-r from-primary to-primary-bright opacity-0 transition-opacity duration-200 group-hover:opacity-100"
        />
      )}
    </article>
  );
}

/** The three-column grid the feature bands use. */
export function CardGrid({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("grid gap-5 sm:grid-cols-2 lg:grid-cols-3", className)}>{children}</div>;
}
