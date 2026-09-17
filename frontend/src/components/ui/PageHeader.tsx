import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

/**
 * The block that opens a page: what this screen is, optionally why, and the
 * one or two actions that belong to the whole screen.
 *
 * Every ported page invented its own — a hero card here, a bare `<h1>` there,
 * an eyebrow-and-gradient panel on the resources list. Having one means the
 * title sits in the same place at the same size on every route, which is most
 * of what makes an app feel like one product.
 */
export function PageHeader({
  title,
  description,
  actions,
  breadcrumb,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  /** Screen-level actions, right-aligned on desktop and stacked on mobile. */
  actions?: ReactNode;
  /** A back link or trail, above the title. */
  breadcrumb?: ReactNode;
  className?: string;
}) {
  return (
    <header className={cn("flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between", className)}>
      <div className="min-w-0">
        {breadcrumb ? <div className="mb-2 text-caption text-ink-muted">{breadcrumb}</div> : null}
        <h1 className="text-page-title text-ink">{title}</h1>
        {description ? <p className="mt-1.5 max-w-2xl text-body text-ink-soft">{description}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}

/**
 * The same idea one level down: the heading that opens a section inside a
 * page. Smaller than a page title and larger than a card title, so the three
 * levels stay distinguishable without anyone choosing a pixel size.
 */
export function SectionHeader({
  title,
  description,
  actions,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-end justify-between gap-3", className)}>
      <div className="min-w-0">
        <h2 className="text-section-title text-ink">{title}</h2>
        {description ? <p className="mt-1 text-body-sm text-ink-soft">{description}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}
