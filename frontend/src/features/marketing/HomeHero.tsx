import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui";

/**
 * The homepage hero. It lives in `<header>` rather than in `<main>` because
 * that is where the design puts it: the header's gradient runs behind nav and
 * hero as one surface, and splitting them onto two elements would restart the
 * gradient halfway down.
 *
 * `PublicShell` passes it to `AppShell` as `headerExtra` on `/` only.
 */
export function HomeHero() {
  const { t } = useTranslation();

  const stats = [
    { title: t("home.showcase.stat1Title"), body: t("home.showcase.stat1Body") },
    { title: t("home.showcase.stat2Title"), body: t("home.showcase.stat2Body") },
    { title: t("home.showcase.stat3Title"), body: t("home.showcase.stat3Body") },
  ];

  const proof = [t("home.hero.proof1"), t("home.hero.proof2"), t("home.hero.proof3")];

  return (
    <div className="px-4 pt-10 pb-20">
      <div className="mx-auto grid max-w-content items-center gap-12 lg:grid-cols-2">
        <div className="max-w-xl">
          <span className="inline-flex rounded-full bg-ink/20 px-3 py-1 text-overline text-white uppercase">
            {t("home.hero.kicker")}
          </span>

          {/* The page's only `h1`. The nav above it is a landmark, not a
            * heading, so this is where the document outline starts. */}
          <h1 className="mt-5 text-4xl leading-[1.1] font-bold tracking-tight text-balance text-white sm:text-5xl">
            {t("home.hero.title")}
          </h1>
          <p className="mt-5 text-lg text-pretty text-white/80">{t("home.hero.body")}</p>

          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link to="/register">
              {/* Ink on the bright mint: white on it measured 1.6:1, and this
                * is the most important control on the site. */}
              <Button size="lg" className="bg-primary-bright text-ink hover:bg-primary-muted">
                {t("home.hero.primaryCta")}
              </Button>
            </Link>
            <Link
              to="/about"
              className="rounded-md px-3 py-2 text-body-sm font-medium text-white underline underline-offset-4 transition-colors hover:text-primary-bright"
            >
              {t("home.hero.secondaryCta")}
            </Link>
          </div>

          <ul className="mt-8 flex flex-wrap gap-2">
            {proof.map((item) => (
              <li
                key={item}
                className="rounded-full border border-white/25 bg-ink/15 px-3 py-1 text-caption text-white/90"
              >
                {item}
              </li>
            ))}
          </ul>
        </div>

        <div className="flex flex-col gap-4">
          <article className="rounded-xl border border-white/20 bg-surface p-6 shadow-lg">
            <span className="inline-flex rounded-full bg-primary-subtle px-2.5 py-1 text-overline text-primary uppercase">
              {t("home.showcase.primaryLabel")}
            </span>
            <h2 className="mt-3 text-section-title text-ink">{t("home.showcase.primaryTitle")}</h2>
            <p className="mt-2 text-body-sm text-ink-soft">{t("home.showcase.primaryBody")}</p>

            <dl className="mt-5 grid grid-cols-3 gap-2">
              {stats.map((stat) => (
                <div key={stat.title} className="rounded-md bg-ink p-3">
                  <dt className="text-label text-white">{stat.title}</dt>
                  <dd className="mt-0.5 text-caption text-white/60">{stat.body}</dd>
                </div>
              ))}
            </dl>
          </article>

          <article className="flex items-center gap-3 rounded-xl border border-white/20 bg-white/10 p-5 backdrop-blur-sm">
            <span className="shrink-0 rounded-full bg-ink/25 px-3 py-1 text-overline text-white uppercase">
              {t("home.showcase.secondaryBadge")}
            </span>
            <p className="text-body-sm text-white/85">{t("home.showcase.secondaryBody")}</p>
          </article>
        </div>
      </div>
    </div>
  );
}
