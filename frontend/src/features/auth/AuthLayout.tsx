import { Arrow } from "@/components/ui";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

/**
 * The frame both auth screens share: a brand panel and the form beside it.
 *
 * Login and register were two copies of this markup with different copy, which
 * is how they drifted into different card radii and two different submit
 * buttons.
 *
 * The panel is decoration — it is hidden below `lg` so the form is the whole
 * screen on a phone rather than something you scroll past a hero to reach.
 */
export function AuthLayout({
  kicker,
  heroTitle,
  heroBody,
  points,
  title,
  subtitle,
  children,
  footer,
}: {
  kicker: string;
  heroTitle: string;
  heroBody: string;
  points: ReactNode;
  title: string;
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
}) {
  const { t } = useTranslation();

  return (
    <div className="grid min-h-screen bg-canvas lg:grid-cols-2">
      <aside className="hidden flex-col justify-between bg-primary p-10 text-white lg:flex">
        <Link to="/" aria-label={t("app.name")} className="inline-flex">
          <img src="/images/logo.png" alt={t("layout.logoAlt")} width={316} height={160} className="h-10 w-auto" />
        </Link>

        <div className="max-w-md">
          <p className="text-overline text-white/70 uppercase">{kicker}</p>
          <h1 className="mt-3 text-display text-white">{heroTitle}</h1>
          <p className="mt-4 text-body text-white/80">{heroBody}</p>
          <div className="mt-8 flex flex-col gap-5">{points}</div>
        </div>

        <p className="text-caption text-white/60">
          {t("layout.footer.copyright", { year: new Date().getFullYear() })}
        </p>
      </aside>

      <main className="flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-sm">
          <Link
            to="/"
            className="mb-6 inline-flex items-center gap-1 text-body-sm text-ink-soft transition-colors hover:text-ink"
          >
            <Arrow direction="back" />
            {t("auth.backToHome")}
          </Link>

          {/* The logo only appears on small screens, where the brand panel that
            * normally carries it is hidden. */}
          <img
            src="/images/logo.png"
            alt={t("layout.logoAlt")}
            width={316}
            height={160}
            className="mb-6 h-10 w-auto lg:hidden"
          />

          <h2 className="text-page-title text-ink">{title}</h2>
          <p className="mt-1.5 text-body-sm text-ink-soft">{subtitle}</p>

          <div className="mt-6 flex flex-col gap-4">{children}</div>

          <div className="mt-6 flex flex-col gap-1.5 text-body-sm text-ink-soft">{footer}</div>
        </div>
      </main>
    </div>
  );
}
