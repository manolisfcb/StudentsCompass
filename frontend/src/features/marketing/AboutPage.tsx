import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { DocumentMeta, PUBLIC_BASE_URL } from "@/components/seo/DocumentMeta";
import { ReferenceModal } from "@/features/marketing/ReferenceModal";

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
    <div className="space-y-20">
      <DocumentMeta
        title={t("about.seoTitle")}
        description={t("about.seoDescription")}
        path="/about"
        jsonLd={ABOUT_JSON_LD}
      />

      <section className="full-bleed hero-gradient -mt-8 space-y-6 px-4 py-14 text-center md:py-20">
        <h1 className="text-4xl font-bold text-white">
          {t("about.hero.titleLine1")}
          <br />
          {t("about.hero.titleLine2")}
        </h1>
        <p className="mx-auto max-w-2xl text-lg text-white/85">{t("about.hero.tagline")}</p>
        <div className="flex flex-wrap items-center justify-center gap-4">
          <Link
            to="/register"
            className="rounded-full bg-white px-5 py-2.5 text-sm font-bold text-brand shadow-[0_14px_28px_rgba(15,23,42,0.16)] hover:bg-[#f0fdfa]"
          >
            {t("about.hero.primaryCta")}
          </Link>
          <a
            href="#for-employers"
            className="rounded-full border border-white/40 px-5 py-2.5 text-sm font-semibold text-white hover:bg-white/10"
          >
            {t("about.hero.secondaryCta")}
          </a>
        </div>
      </section>

      <aside className="rounded-lg border border-border bg-surface p-4 text-center text-sm text-ink-soft">
        {t("about.partnership.prefix")}{" "}
        <a href="https://qevuno.com/" target="_blank" rel="noopener noreferrer" className="text-brand hover:underline">
          qevuno
        </a>
        , {t("about.partnership.suffix")}
      </aside>

      <section className="space-y-8">
        <SectionHead eyebrow={t("about.stats.eyebrow")} title={t("about.stats.title")} />
        <div className="grid gap-4 sm:grid-cols-3">
          {stats.map((stat, index) => (
            <button
              key={stat.value}
              type="button"
              onClick={() => setOpenStat(index)}
              className="rounded-lg border border-border bg-surface p-6 text-left hover:border-brand"
            >
              <span className="text-3xl font-bold text-brand">{stat.value}</span>
              <p className="mt-2 text-sm text-ink-soft">{stat.body}</p>
              <span className="mt-3 block text-xs font-medium text-brand">{t("about.stats.viewSource")}</span>
            </button>
          ))}
        </div>
        <p className="text-center text-ink-soft">{t("about.stats.conclusion")}</p>
      </section>

      {openStat !== null && stats[openStat] ? (
        <ReferenceModal
          title={stats[openStat].citationTitle}
          paragraphs={stats[openStat].citation}
          url={stats[openStat].url}
          secondaryUrl={stats[openStat].secondaryUrl}
          onClose={() => setOpenStat(null)}
        />
      ) : null}

      <section id="for-employers" className="space-y-8">
        <Badge>{t("about.employers.badge")}</Badge>
        <SectionHead title={t("about.employers.title")} intro={t("about.employers.intro")} />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {employerValues.map((item) => (
            <FeatureCard key={item.title} {...item} />
          ))}
        </div>
      </section>

      <section className="rounded-lg bg-ink p-8 text-white">
        <SectionHead
          eyebrow={t("about.roi.eyebrow")}
          title={t("about.roi.title")}
          eyebrowClassName="text-brand-soft"
          titleClassName="text-white"
        />
        <div className="mt-6 grid gap-6 sm:grid-cols-2">
          <div>
            <h3 className="font-semibold text-white/80">{t("about.roi.traditional.title")}</h3>
            <ul className="mt-3 space-y-2 text-sm text-white/70">
              {traditionalHiring.map((item) => (
                <li key={item}>✕ {item}</li>
              ))}
            </ul>
          </div>
          <div className="rounded-lg bg-white/10 p-4">
            <span className="text-xs font-semibold uppercase tracking-wide text-brand-soft">
              {t("about.roi.compass.recommended")}
            </span>
            <h3 className="mt-1 font-semibold text-white">{t("about.roi.compass.title")}</h3>
            <ul className="mt-3 space-y-2 text-sm text-white/90">
              {compassHiring.map((item) => (
                <li key={item}>✓ {item}</li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section className="space-y-8">
        <SectionHead
          eyebrow={t("about.framework.eyebrow")}
          title={t("about.framework.title")}
          intro={t("about.framework.intro")}
        />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {frameworkItems.map((item) => (
            <FeatureCard key={item.title} {...item} />
          ))}
        </div>
        <p className="text-sm italic text-ink-muted">{t("about.framework.disclaimer")}</p>
      </section>

      <section className="space-y-8">
        <SectionHead eyebrow={t("about.outcomes.eyebrow")} title={t("about.outcomes.title")} />
        <div className="grid gap-4 sm:grid-cols-2">
          {outcomes.map((outcome) => (
            <div key={outcome.body} className="flex gap-3 rounded-lg border border-border bg-surface p-4">
              <span aria-hidden="true" className="text-xl">
                {outcome.icon}
              </span>
              <p className="text-sm text-ink-soft">{outcome.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-8">
        <Badge>{t("about.students.badge")}</Badge>
        <SectionHead title={t("about.students.title")} intro={t("about.students.intro")} />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {studentFeatures.map((item) => (
            <FeatureCard key={item.title} {...item} />
          ))}
        </div>
      </section>

      <section className="space-y-8">
        <SectionHead
          eyebrow={t("about.philosophy.eyebrow")}
          title={t("about.philosophy.title")}
          intro={t("about.philosophy.intro")}
        />
        <div className="grid gap-6 sm:grid-cols-2">
          <div>
            <h3 className="font-semibold text-ink">{t("about.philosophy.believe.title")}</h3>
            <ul className="mt-3 space-y-2 text-sm text-ink-soft">
              {believeList.map((item) => (
                <li key={item}>✅ {item}</li>
              ))}
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-ink">{t("about.philosophy.not.title")}</h3>
            <ul className="mt-3 space-y-2 text-sm text-ink-soft">
              {notList.map((item) => (
                <li key={item}>❌ {item}</li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg bg-brand p-8 text-white">
          <span className="text-xs font-semibold uppercase tracking-wide text-brand-soft">
            {t("about.dualCta.employer.label")}
          </span>
          <h2 className="mt-2 text-xl font-bold">{t("about.dualCta.employer.title")}</h2>
          <p className="mt-2 text-sm text-white/90">{t("about.dualCta.employer.body")}</p>
          <Link
            to="/register"
            className="mt-4 inline-block rounded-md bg-white px-4 py-2 text-sm font-semibold text-brand hover:bg-canvas"
          >
            {t("about.dualCta.employer.button")}
          </Link>
        </div>
        <div className="rounded-lg bg-ink p-8 text-white">
          <span className="text-xs font-semibold uppercase tracking-wide text-brand-soft">
            {t("about.dualCta.student.label")}
          </span>
          <h2 className="mt-2 text-xl font-bold">{t("about.dualCta.student.title")}</h2>
          <p className="mt-2 text-sm text-white/90">{t("about.dualCta.student.body")}</p>
          <Link
            to="/register"
            className="mt-4 inline-block rounded-md bg-white px-4 py-2 text-sm font-semibold text-ink hover:bg-canvas"
          >
            {t("about.dualCta.student.button")}
          </Link>
        </div>
      </section>
    </div>
  );
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-block rounded-full bg-brand/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-brand">
      {children}
    </span>
  );
}

function SectionHead({
  eyebrow,
  title,
  intro,
  eyebrowClassName = "text-brand",
  titleClassName = "text-ink",
}: {
  eyebrow?: string;
  title: string;
  intro?: string;
  eyebrowClassName?: string;
  titleClassName?: string;
}) {
  return (
    <div className="max-w-2xl space-y-2">
      {eyebrow ? (
        <span className={`text-sm font-semibold uppercase tracking-wide ${eyebrowClassName}`}>{eyebrow}</span>
      ) : null}
      <h2 className={`text-2xl font-bold ${titleClassName}`}>{title}</h2>
      {intro ? <p className="text-ink-soft">{intro}</p> : null}
    </div>
  );
}

function FeatureCard({ icon, title, body }: { icon: string; title: string; body: string }) {
  return (
    <article className="rounded-lg border border-border bg-surface p-5">
      <span aria-hidden="true" className="text-2xl">
        {icon}
      </span>
      <h3 className="mt-2 font-semibold text-ink">{title}</h3>
      <p className="mt-1 text-sm text-ink-soft">{body}</p>
    </article>
  );
}
