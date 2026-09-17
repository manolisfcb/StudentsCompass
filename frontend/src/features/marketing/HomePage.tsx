import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { DocumentMeta } from "@/components/seo/DocumentMeta";

/**
 * The homepage, ported from `home.html` over `style.css`'s marketing rules.
 * The hero is not here: it belongs inside the shell's `<header>`, so it lives
 * in `HomeHero` and `PublicShell` places it (see that file for why).
 *
 * (TASK-046). Content is carried over verbatim from
 * `backend/app/templates/home.html`: this vertical moves the presentation
 * layer, not the copy — inventing marketing copy here would be exactly the
 * kind of undocumented change Scope forbids.
 *
 * Every card below is built from literal translation calls rather than a
 * template-literal key: `tools/check-i18n.mjs` only recognises literal keys,
 * on purpose — a computed key is exactly the kind of reference a static
 * checker cannot verify against the catalogue, so the codebase does not use
 * them.
 */

export function HomePage() {
  const { t } = useTranslation();

  const studentFeatures = [
    { icon: "📝", title: t("home.students.features.0.title"), body: t("home.students.features.0.body") },
    { icon: "💼", title: t("home.students.features.1.title"), body: t("home.students.features.1.body") },
    { icon: "🎯", title: t("home.students.features.2.title"), body: t("home.students.features.2.body") },
    { icon: "📚", title: t("home.students.features.3.title"), body: t("home.students.features.3.body") },
    { icon: "👥", title: t("home.students.features.4.title"), body: t("home.students.features.4.body") },
    { icon: "📊", title: t("home.students.features.5.title"), body: t("home.students.features.5.body") },
  ];

  const companyFeatures = [
    { icon: "🎓", title: t("home.companies.features.0.title"), body: t("home.companies.features.0.body") },
    { icon: "💡", title: t("home.companies.features.1.title"), body: t("home.companies.features.1.body") },
    { icon: "🔍", title: t("home.companies.features.2.title"), body: t("home.companies.features.2.body") },
    { icon: "📈", title: t("home.companies.features.3.title"), body: t("home.companies.features.3.body") },
    { icon: "🤝", title: t("home.companies.features.4.title"), body: t("home.companies.features.4.body") },
    { icon: "⚡", title: t("home.companies.features.5.title"), body: t("home.companies.features.5.body") },
  ];

  const platformItems = [
    { image: "roadmap", title: t("home.platform.items.0.title"), body: t("home.platform.items.0.body") },
    { image: "goal", title: t("home.platform.items.1.title"), body: t("home.platform.items.1.body") },
    { image: "resources", title: t("home.platform.items.2.title"), body: t("home.platform.items.2.body") },
  ];

  const steps = [
    { number: "1", title: t("home.steps.items.0.title"), body: t("home.steps.items.0.body") },
    { number: "2", title: t("home.steps.items.1.title"), body: t("home.steps.items.1.body") },
    { number: "3", title: t("home.steps.items.2.title"), body: t("home.steps.items.2.body") },
  ];

  const testimonials = [
    { quote: t("home.testimonials.items.0.quote"), author: t("home.testimonials.items.0.author") },
    { quote: t("home.testimonials.items.1.quote"), author: t("home.testimonials.items.1.author") },
  ];

  return (
    <>
      <DocumentMeta title={t("home.seoTitle")} description={t("home.seoDescription")} path="/" />

      <section className="home-value-strip">
        <div className="container">
          <div className="value-strip-grid">
            <ValuePill title={t("home.value.students.title")} body={t("home.value.students.body")} />
            <ValuePill title={t("home.value.companies.title")} body={t("home.value.companies.body")} />
            <ValuePill title={t("home.value.platform.title")} body={t("home.value.platform.body")} />
          </div>
        </div>
      </section>

      <section id="for-students" className="home-audience-section home-audience-section-students">
        <div className="container">
          <SectionHead
            kicker={t("home.students.kicker")}
            title={t("home.students.title")}
            intro={t("home.students.intro")}
          />
          <div className="feature-cards feature-cards-home">
            {studentFeatures.map((feature) => (
              <FeatureCard key={feature.title} {...feature} />
            ))}
          </div>
        </div>
      </section>

      <section id="for-companies" className="home-audience-section home-audience-section-companies">
        <div className="container">
          <SectionHead
            kicker={t("home.companies.kicker")}
            title={t("home.companies.title")}
            intro={t("home.companies.intro")}
            kickerDark
          />
          <div className="feature-cards feature-cards-home">
            {companyFeatures.map((feature) => (
              <FeatureCard key={feature.title} {...feature} />
            ))}
          </div>
        </div>
      </section>

      <section id="features" className="home-platform-section">
        <div className="container">
          <SectionHead
            kicker={t("home.platform.kicker")}
            title={t("home.platform.title")}
            intro={t("home.platform.intro")}
          />
          <div className="feature-cards feature-cards-home feature-cards-visual">
            {platformItems.map((item) => (
              <div key={item.image} className="card home-card home-card-visual">
                <img src={`/images/${item.image}.svg`} alt={item.title} />
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="how-it-works" className="how-it-works home-journey-section">
        <div className="container">
          <SectionHead kicker={t("home.steps.kicker")} title={t("home.steps.title")} />
          <div className="steps">
            {steps.map((step) => (
              <div key={step.number} className="step home-step">
                <span>{step.number}</span>
                <h3>{step.title}</h3>
                <p>{step.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="testimonials" className="testimonials home-social-proof">
        <div className="container">
          <SectionHead kicker={t("home.testimonials.kicker")} title={t("home.testimonials.title")} />
          <div className="testimonial-cards">
            {testimonials.map((testimonial) => (
              <div key={testimonial.author} className="card home-card testimonial-card">
                <p>{testimonial.quote}</p>
                <span>{testimonial.author}</span>
              </div>
            ))}
          </div>
          <div className="home-final-cta">
            <h3>{t("home.finalCta.title")}</h3>
            <Link to="/register" className="cta-button">
              {t("home.finalCta.button")}
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}

function ValuePill({ title, body }: { title: string; body: string }) {
  return (
    <div className="value-pill">
      <strong>{title}</strong>
      <span>{body}</span>
    </div>
  );
}

function SectionHead({
  kicker,
  title,
  intro,
  kickerDark = false,
}: {
  kicker: string;
  title: string;
  intro?: string;
  /** `.section-kicker-dark` — the variant the companies band uses. */
  kickerDark?: boolean;
}) {
  return (
    <div className="home-section-head">
      <span className={`section-kicker${kickerDark ? " section-kicker-dark" : ""}`}>{kicker}</span>
      <h2>{title}</h2>
      {intro ? <p className="section-intro">{intro}</p> : null}
    </div>
  );
}

function FeatureCard({ icon, title, body }: { icon: string; title: string; body: string }) {
  return (
    <div className="card home-card">
      <span className="home-card-icon" aria-hidden="true">
        {icon}
      </span>
      <h3>{title}</h3>
      <p>{body}</p>
    </div>
  );
}
