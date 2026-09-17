import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { DocumentMeta, PUBLIC_BASE_URL } from "@/components/seo/DocumentMeta";
import { Arrow, Badge, Button } from "@/components/ui";
import { ReferenceModal } from "@/features/marketing/ReferenceModal";
import { Band, CardGrid, MarketingCard, SectionHead } from "@/features/marketing/sections";

/**
 * `/about` (TASK-046). Content carried over verbatim from
 * `backend/app/templates/about.html`; the citation data below is
 * `aboutRefData` from `about.js`, unchanged.
 *
 * As in `HomePage`, every card is built from literal translation calls: the
 * `i18n:check` lane only resolves keys it can find written out in source.
 */

interface Stat {
  value: string;
  body: string;
  citationTitle: string;
  citation: string[];
  url: string;
  secondaryUrl?: string;
}

const ABOUT_JSON_LD = {
  "@context": "https://schema.org",
  "@type": "AboutPage",
  name: "About Students Compass",
  url: `${PUBLIC_BASE_URL}/about`,
  description:
    "Learn how Student Compass prepares career-ready graduates for Canadian employers, in partnership with qevuno's private, ad-free app ecosystem.",
  mainEntity: { "@type": "Organization", name: "Students Compass", url: `${PUBLIC_BASE_URL}/` },
  mentions: { "@type": "Organization", name: "qevuno", url: "https://qevuno.com/" },
  relatedLink: "https://qevuno.com/",
};

export function AboutPage() {
  const { t } = useTranslation();
  const [openStat, setOpenStat] = useState<number | null>(null);

  const stats: Stat[] = [
    {
      value: "49%",
      body: t("about.stats.items.0.body"),
      citationTitle: t("about.stats.items.0.citationTitle"),
      citation: [t("about.stats.items.0.citation.0"), t("about.stats.items.0.citation.1"), t("about.stats.items.0.citation.2")],
      url: "https://www.expresspros.ca/newsroom/news-releases/news-releases/2025/02/canadian-companies-say-worsening-skills-gap-and-navigating-ai-top-challenges-in-2025",
    },
    {
      value: "$30,680",
      body: t("about.stats.items.1.body"),
      citationTitle: t("about.stats.items.1.citationTitle"),
      citation: [
        t("about.stats.items.1.citation.0"),
        t("about.stats.items.1.citation.1"),
        t("about.stats.items.1.citation.2"),
        t("about.stats.items.1.citation.3"),
      ],
      url: "https://www.expresspros.ca/newsroom/news-releases/news-releases/2025/12/canadian-hiring-outlook-dampens-in-first-half-of-2026",
      secondaryUrl:
        "https://press.roberthalf.ca/2025-12-10-Survey-One-third-of-Canadian-professionals-plan-to-search-for-a-new-job-in-2026",
    },
    {
      value: "82%",
      body: t("about.stats.items.2.body"),
      citationTitle: t("about.stats.items.2.citationTitle"),
      citation: [t("about.stats.items.2.citation.0"), t("about.stats.items.2.citation.1"), t("about.stats.items.2.citation.2")],
      url: "https://www.expresspros.com/jobinsights-canada",
    },
  ];

  const employerValues = [
    { icon: "🎯", title: t("about.employers.items.0.title"), body: t("about.employers.items.0.body") },
    { icon: "📝", title: t("about.employers.items.1.title"), body: t("about.employers.items.1.body") },
    { icon: "🎤", title: t("about.employers.items.2.title"), body: t("about.employers.items.2.body") },
    { icon: "💡", title: t("about.employers.items.3.title"), body: t("about.employers.items.3.body") },
    { icon: "📊", title: t("about.employers.items.4.title"), body: t("about.employers.items.4.body") },
    { icon: "🤝", title: t("about.employers.items.5.title"), body: t("about.employers.items.5.body") },
  ];

  const traditionalHiring = [
    t("about.roi.traditional.items.0"),
    t("about.roi.traditional.items.1"),
    t("about.roi.traditional.items.2"),
    t("about.roi.traditional.items.3"),
    t("about.roi.traditional.items.4"),
  ];

  const compassHiring = [
    t("about.roi.compass.items.0"),
    t("about.roi.compass.items.1"),
    t("about.roi.compass.items.2"),
    t("about.roi.compass.items.3"),
    t("about.roi.compass.items.4"),
  ];

  const frameworkItems = [
    { icon: "🔍", title: t("about.framework.items.0.title"), body: t("about.framework.items.0.body") },
    { icon: "📋", title: t("about.framework.items.1.title"), body: t("about.framework.items.1.body") },
    { icon: "🎤", title: t("about.framework.items.2.title"), body: t("about.framework.items.2.body") },
    { icon: "🎯", title: t("about.framework.items.3.title"), body: t("about.framework.items.3.body") },
  ];

  const outcomes = [
    { icon: "🎯", body: t("about.outcomes.items.0") },
    { icon: "📄", body: t("about.outcomes.items.1") },
    { icon: "🗣️", body: t("about.outcomes.items.2") },
    { icon: "💎", body: t("about.outcomes.items.3") },
  ];

  const studentFeatures = [
    { icon: "📝", title: t("about.students.items.0.title"), body: t("about.students.items.0.body") },
    { icon: "💼", title: t("about.students.items.1.title"), body: t("about.students.items.1.body") },
    { icon: "🎯", title: t("about.students.items.2.title"), body: t("about.students.items.2.body") },
    { icon: "📚", title: t("about.students.items.3.title"), body: t("about.students.items.3.body") },
    { icon: "👥", title: t("about.students.items.4.title"), body: t("about.students.items.4.body") },
    { icon: "📊", title: t("about.students.items.5.title"), body: t("about.students.items.5.body") },
  ];

  const believeList = [
    t("about.philosophy.believe.items.0"),
    t("about.philosophy.believe.items.1"),
    t("about.philosophy.believe.items.2"),
    t("about.philosophy.believe.items.3"),
  ];

  const notList = [
    t("about.philosophy.not.items.0"),
    t("about.philosophy.not.items.1"),
    t("about.philosophy.not.items.2"),
    t("about.philosophy.not.items.3"),
  ];

  return (
    <>
      <DocumentMeta
        title={t("about.seoTitle")}
        description={t("about.seoDescription")}
        path="/about"
        jsonLd={ABOUT_JSON_LD}
      />

      <Band tone="brand" className="py-20 sm:py-24">
        <div className="mx-auto max-w-3xl text-center">
          <h1 className="text-4xl leading-[1.1] font-bold tracking-tight text-balance text-white sm:text-5xl">
            {t("about.hero.titleLine1")}
            <br />
            {t("about.hero.titleLine2")}
          </h1>
          <p className="mx-auto mt-5 max-w-xl text-lg text-pretty text-white/75">{t("about.hero.tagline")}</p>

          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link to="/register">
              <Button size="lg" className="bg-primary-bright text-ink hover:bg-primary-muted">
                {t("about.hero.primaryCta")}
              </Button>
            </Link>
            <a href="#for-employers">
              <Button size="lg" className="border border-white/30 bg-white/10 text-white hover:bg-white/20">
                {t("about.hero.secondaryCta")} <span aria-hidden="true">↓</span>
              </Button>
            </a>
          </div>
        </div>
      </Band>

      <aside aria-label={t("about.partnership.label")} className="border-b border-border bg-surface px-4 py-3">
        <p className="mx-auto max-w-content text-center text-caption text-ink-soft">
          {t("about.partnership.prefix")}{" "}
          <a
            href="https://qevuno.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-primary underline underline-offset-2 hover:text-primary-hover"
          >
            qevuno
          </a>
          , {t("about.partnership.suffix")}
        </p>
      </aside>

      <Band tone="canvas">
        <SectionHead kicker={t("about.stats.eyebrow")} title={t("about.stats.title")} />

        <div className="grid gap-5 sm:grid-cols-3">
          {stats.map((stat, index) => (
            // A real button, not a `role="button"` div with a hand-rolled
            // keydown handler: Enter, Space, focus and the announced role all
            // come free, and there is no keyboard behaviour left to get wrong.
            <button
              key={stat.value}
              type="button"
              aria-label={t("about.stats.viewSourceFor", { value: stat.value })}
              onClick={() => setOpenStat(index)}
              className="group flex flex-col items-center rounded-lg border border-border bg-surface p-6 text-center shadow-xs transition-[transform,box-shadow,border-color] duration-200 hover:-translate-y-0.5 hover:border-border-strong hover:shadow-md"
            >
              <span className="text-display text-primary tabular-nums">{stat.value}</span>
              <p className="mt-3 text-body-sm text-ink-soft">{stat.body}</p>
              <span className="mt-4 text-caption font-medium text-primary group-hover:text-primary-hover">
                {t("about.stats.viewSource")}
              </span>
            </button>
          ))}
        </div>

        <p className="mx-auto mt-10 max-w-2xl text-center text-body font-medium text-balance text-ink">
          {t("about.stats.conclusion")}
        </p>
      </Band>

      {openStat !== null && stats[openStat] ? (
        <ReferenceModal
          title={stats[openStat].citationTitle}
          paragraphs={stats[openStat].citation}
          url={stats[openStat].url}
          secondaryUrl={stats[openStat].secondaryUrl}
          onClose={() => setOpenStat(null)}
        />
      ) : null}

      <Band id="for-employers" tone="tint">
        <div className="mb-4 flex justify-center">
          <Badge tone="brand" size="md">
            {t("about.employers.badge")}
          </Badge>
        </div>
        <SectionHead title={t("about.employers.title")} intro={t("about.employers.intro")} />
        <CardGrid>
          {employerValues.map((item) => (
            <MarketingCard key={item.title} icon={item.icon} title={item.title} body={item.body} />
          ))}
        </CardGrid>
      </Band>

      <Band tone="dark">
        <SectionHead kicker={t("about.roi.eyebrow")} title={t("about.roi.title")} onDark />

        <div className="grid gap-5 lg:grid-cols-2">
          <div className="rounded-lg border border-white/10 bg-white/5 p-6">
            <h3 className="text-section-title text-white">{t("about.roi.traditional.title")}</h3>
            <ul className="mt-4 flex flex-col gap-2.5">
              {traditionalHiring.map((item) => (
                <li key={item} className="flex gap-2.5 text-body-sm text-white/70">
                  <span aria-hidden="true" className="text-danger">
                    ✕
                  </span>
                  {item}
                </li>
              ))}
            </ul>
          </div>

          {/* The recommended column is outlined in the brand colour rather than
            * merely tinted, so the comparison has a visible winner. */}
          <div className="relative rounded-lg border-2 border-primary-bright bg-white/10 p-6">
            <span className="absolute -top-3 left-6 rounded-full bg-primary-bright px-3 py-0.5 text-overline text-ink uppercase">
              {t("about.roi.compass.recommended")}
            </span>
            <h3 className="text-section-title text-white">{t("about.roi.compass.title")}</h3>
            <ul className="mt-4 flex flex-col gap-2.5">
              {compassHiring.map((item) => (
                <li key={item} className="flex gap-2.5 text-body-sm text-white/85">
                  <span aria-hidden="true" className="text-primary-bright">
                    ✓
                  </span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Band>

      <Band tone="surface">
        <SectionHead
          kicker={t("about.framework.eyebrow")}
          title={t("about.framework.title")}
          intro={t("about.framework.intro")}
        />
        <div className="grid gap-5 sm:grid-cols-2">
          {frameworkItems.map((item) => (
            <MarketingCard key={item.title} icon={item.icon} title={item.title} body={item.body} />
          ))}
        </div>
        <p className="mt-8 text-center text-caption text-ink-muted">{t("about.framework.disclaimer")}</p>
      </Band>

      <Band tone="canvas">
        <SectionHead kicker={t("about.outcomes.eyebrow")} title={t("about.outcomes.title")} />
        <ul className="grid gap-4 sm:grid-cols-2">
          {outcomes.map((outcome) => (
            <li
              key={outcome.body}
              className="flex items-center gap-3 rounded-lg border border-border bg-surface p-4 shadow-xs"
            >
              <span
                aria-hidden="true"
                className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary-subtle text-lg"
              >
                {outcome.icon}
              </span>
              <p className="text-body-sm text-ink-soft">{outcome.body}</p>
            </li>
          ))}
        </ul>
      </Band>

      <Band tone="tint">
        <div className="mb-4 flex justify-center">
          <Badge tone="brand" size="md">
            {t("about.students.badge")}
          </Badge>
        </div>
        <SectionHead title={t("about.students.title")} intro={t("about.students.intro")} />
        <CardGrid>
          {studentFeatures.map((item) => (
            <MarketingCard key={item.title} icon={item.icon} title={item.title} body={item.body} />
          ))}
        </CardGrid>
      </Band>

      <Band tone="surface">
        <SectionHead
          kicker={t("about.philosophy.eyebrow")}
          title={t("about.philosophy.title")}
          intro={t("about.philosophy.intro")}
        />
        <div className="grid gap-5 lg:grid-cols-2">
          <div className="rounded-lg border border-success-border bg-success-subtle p-6">
            <h3 className="text-section-title text-ink">{t("about.philosophy.believe.title")}</h3>
            <ul className="mt-4 flex flex-col gap-2.5">
              {believeList.map((item) => (
                <li key={item} className="flex gap-2.5 text-body-sm text-ink-soft">
                  <span aria-hidden="true" className="text-success">
                    ✓
                  </span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-lg border border-danger-border bg-danger-subtle p-6">
            <h3 className="text-section-title text-ink">{t("about.philosophy.not.title")}</h3>
            <ul className="mt-4 flex flex-col gap-2.5">
              {notList.map((item) => (
                <li key={item} className="flex gap-2.5 text-body-sm text-ink-soft">
                  <span aria-hidden="true" className="text-danger">
                    ✕
                  </span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Band>

      <Band tone="dark">
        <div className="grid gap-5 lg:grid-cols-2">
          {[
            {
              label: t("about.dualCta.employer.label"),
              title: t("about.dualCta.employer.title"),
              body: t("about.dualCta.employer.body"),
              button: t("about.dualCta.employer.button"),
            },
            {
              label: t("about.dualCta.student.label"),
              title: t("about.dualCta.student.title"),
              body: t("about.dualCta.student.body"),
              button: t("about.dualCta.student.button"),
            },
          ].map((cta) => (
            <div key={cta.label} className="rounded-xl border border-white/15 bg-white/5 p-8">
              <span className="text-overline text-primary-bright uppercase">{cta.label}</span>
              <h2 className="mt-3 text-section-title text-balance text-white">{cta.title}</h2>
              <p className="mt-2 text-body-sm text-white/70">{cta.body}</p>
              <Link to="/register" className="mt-6 inline-flex">
                <Button className="bg-surface text-ink hover:bg-white/90">
                  {cta.button} <Arrow direction="forward" />
                </Button>
              </Link>
            </div>
          ))}
        </div>
      </Band>
    </>
  );
}
