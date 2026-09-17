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
    <>
      <DocumentMeta
        title={t("about.seoTitle")}
        description={t("about.seoDescription")}
        path="/about"
        jsonLd={ABOUT_JSON_LD}
      />

      <section className="about-hero">
        <div className="container">
          <h1>
            {t("about.hero.titleLine1")}
            <br />
            {t("about.hero.titleLine2")}
          </h1>
          <p className="about-tagline">{t("about.hero.tagline")}</p>
          <div className="hero-dual-cta">
            <Link to="/register" className="about-btn about-btn--primary">
              {t("about.hero.primaryCta")}
            </Link>
            <a href="#for-employers" className="about-btn about-btn--ghost">
              {t("about.hero.secondaryCta")}
            </a>
          </div>
        </div>
      </section>

      <aside className="about-partnership" aria-label={t("about.partnership.label")}>
        <div className="container">
          <p>
            {t("about.partnership.prefix")}{" "}
            <a href="https://qevuno.com/" target="_blank" rel="noopener noreferrer">
              qevuno
            </a>
            , {t("about.partnership.suffix")}
          </p>
        </div>
      </aside>

      <section className="about-section about-section--stats">
        <div className="container">
          <span className="section-eyebrow">{t("about.stats.eyebrow")}</span>
          <h2>{t("about.stats.title")}</h2>
          <div className="about-problem-grid">
            {stats.map((stat, index) => (
              <div
                key={stat.value}
                className="problem-card problem-card--clickable"
                role="button"
                tabIndex={0}
                aria-label={t("about.stats.viewSourceFor", { value: stat.value })}
                onClick={() => setOpenStat(index)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setOpenStat(index);
                  }
                }}
              >
                <span className="problem-stat">{stat.value}</span>
                <p>{stat.body}</p>
                <span className="problem-card__source-hint">{t("about.stats.viewSource")}</span>
              </div>
            ))}
          </div>
          <p className="problem-conclusion">{t("about.stats.conclusion")}</p>
        </div>
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

      <section id="for-employers" className="about-section about-section-employer">
        <div className="container">
          <div className="employer-badge">{t("about.employers.badge")}</div>
          <h2>{t("about.employers.title")}</h2>
          <p className="section-intro">{t("about.employers.intro")}</p>
          <div className="employer-value-grid">
            {employerValues.map((item) => (
              <div key={item.title} className="employer-value-card">
                <div className="evc-icon-wrap">
                  <span className="evc-icon" aria-hidden="true">
                    {item.icon}
                  </span>
                </div>
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="about-section about-roi">
        <div className="container">
          <span className="section-eyebrow section-eyebrow--light">{t("about.roi.eyebrow")}</span>
          <h2>{t("about.roi.title")}</h2>
          <div className="roi-comparison">
            <div className="roi-column roi-traditional">
              <h3>{t("about.roi.traditional.title")}</h3>
              <ul>
                {traditionalHiring.map((item) => (
                  <li key={item}>
                    <span className="roi-x" aria-hidden="true">
                      ✕
                    </span>{" "}
                    {item}
                  </li>
                ))}
              </ul>
            </div>
            <div className="roi-column roi-compass">
              <div className="roi-recommended">{t("about.roi.compass.recommended")}</div>
              <h3>{t("about.roi.compass.title")}</h3>
              <ul>
                {compassHiring.map((item) => (
                  <li key={item}>
                    <span className="roi-check" aria-hidden="true">
                      ✓
                    </span>{" "}
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section className="about-section about-section-alt about-section--framework">
        <div className="container">
          <span className="section-eyebrow">{t("about.framework.eyebrow")}</span>
          <h2>{t("about.framework.title")}</h2>
          <p className="section-intro">{t("about.framework.intro")}</p>
          <div className="framework-grid">
            {frameworkItems.map((item) => (
              <div key={item.title} className="framework-card">
                <div className="evc-icon-wrap">
                  <span className="evc-icon" aria-hidden="true">
                    {item.icon}
                  </span>
                </div>
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </div>
            ))}
          </div>
          <p className="framework-disclaimer">{t("about.framework.disclaimer")}</p>
        </div>
      </section>

      <section className="about-section about-section--outcomes">
        <div className="container">
          <span className="section-eyebrow">{t("about.outcomes.eyebrow")}</span>
          <h2>{t("about.outcomes.title")}</h2>
          <div className="about-outcomes employer-outcomes">
            {outcomes.map((outcome) => (
              <div key={outcome.body} className="outcome-item">
                <div className="outcome-icon-wrap">
                  <span className="outcome-icon" aria-hidden="true">
                    {outcome.icon}
                  </span>
                </div>
                <p>{outcome.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="about-section about-section-alt about-section--students">
        <div className="container">
          <div className="employer-badge student-badge">{t("about.students.badge")}</div>
          <h2>{t("about.students.title")}</h2>
          <p className="section-intro">{t("about.students.intro")}</p>
          <div className="about-features-grid">
            {studentFeatures.map((item) => (
              <div key={item.title} className="about-feature">
                <div className="about-feature-icon-wrap">
                  <span className="about-feature-icon" aria-hidden="true">
                    {item.icon}
                  </span>
                </div>
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="about-section about-section--philosophy">
        <div className="container">
          <span className="section-eyebrow">{t("about.philosophy.eyebrow")}</span>
          <h2>{t("about.philosophy.title")}</h2>
          <p className="section-intro">{t("about.philosophy.intro")}</p>
          <div className="about-philosophy">
            <div className="philosophy-item philosophy-positive">
              <h3>{t("about.philosophy.believe.title")}</h3>
              <ul>
                {believeList.map((item) => (
                  <li key={item}>✅ {item}</li>
                ))}
              </ul>
            </div>
            <div className="philosophy-item philosophy-negative">
              <h3>{t("about.philosophy.not.title")}</h3>
              <ul>
                {notList.map((item) => (
                  <li key={item}>❌ {item}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section className="about-dual-cta">
        <div className="container">
          <div className="dual-cta-grid">
            <div className="dual-cta-card dual-cta-employer">
              <span className="dual-cta-label">{t("about.dualCta.employer.label")}</span>
              <h2>{t("about.dualCta.employer.title")}</h2>
              <p>{t("about.dualCta.employer.body")}</p>
              <Link to="/register" className="about-btn about-btn--white">
                {t("about.dualCta.employer.button")}
              </Link>
            </div>
            <div className="dual-cta-card dual-cta-student">
              <span className="dual-cta-label">{t("about.dualCta.student.label")}</span>
              <h2>{t("about.dualCta.student.title")}</h2>
              <p>{t("about.dualCta.student.body")}</p>
              <Link to="/register" className="about-btn about-btn--white">
                {t("about.dualCta.student.button")}
              </Link>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
