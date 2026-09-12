import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { DocumentMeta } from "@/components/seo/DocumentMeta";

/**
 * The homepage (TASK-046). Content is carried over verbatim from
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
    <div className="space-y-20">
      <DocumentMeta title={t("home.seoTitle")} description={t("home.seoDescription")} path="/" />

      <section className="full-bleed hero-gradient -mt-8 px-4 py-14 md:py-20">
        <div className="mx-auto grid max-w-6xl gap-10 md:grid-cols-2 md:items-center">
          <div className="space-y-6">
            <span className="inline-block rounded-full border border-white/30 bg-white/10 px-3 py-1 text-xs font-bold uppercase tracking-wide text-white">
              {t("home.hero.kicker")}
            </span>
            <h1 className="text-4xl font-bold text-white">{t("home.hero.title")}</h1>
            <p className="text-lg text-white/85">{t("home.hero.body")}</p>
            <div className="flex flex-wrap items-center gap-4">
              <Link
                to="/register"
                className="rounded-full bg-white px-5 py-2.5 text-sm font-bold text-brand shadow-[0_14px_28px_rgba(15,23,42,0.16)] hover:bg-[#f0fdfa]"
              >
                {t("home.hero.primaryCta")}
              </Link>
              <Link
                to="/about"
                className="rounded-full border border-white/40 px-5 py-2.5 text-sm font-semibold text-white hover:bg-white/10"
              >
                {t("home.hero.secondaryCta")}
              </Link>
            </div>
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-white/70">
              <span>{t("home.hero.proof1")}</span>
              <span>{t("home.hero.proof2")}</span>
              <span>{t("home.hero.proof3")}</span>
            </div>
          </div>

          <div className="space-y-4">
            <article className="rounded-2xl border border-white/20 bg-surface p-6 shadow-[0_24px_60px_rgba(15,23,42,0.16)]">
              <div className="text-xs font-semibold uppercase tracking-wide text-brand">
                {t("home.showcase.primaryLabel")}
              </div>
              <h3 className="mt-2 text-lg font-semibold text-ink">{t("home.showcase.primaryTitle")}</h3>
              <p className="mt-1 text-sm text-ink-soft">{t("home.showcase.primaryBody")}</p>
              <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
                <div>
                  <strong className="block text-ink">{t("home.showcase.stat1Title")}</strong>
                  <span className="text-ink-muted">{t("home.showcase.stat1Body")}</span>
                </div>
                <div>
                  <strong className="block text-ink">{t("home.showcase.stat2Title")}</strong>
                  <span className="text-ink-muted">{t("home.showcase.stat2Body")}</span>
                </div>
                <div>
                  <strong className="block text-ink">{t("home.showcase.stat3Title")}</strong>
                  <span className="text-ink-muted">{t("home.showcase.stat3Body")}</span>
                </div>
              </div>
            </article>
            <article className="rounded-2xl border border-white/20 bg-ink/25 p-6 text-white shadow-[0_24px_60px_rgba(15,23,42,0.16)]">
              <div className="text-xs font-semibold uppercase tracking-wide text-brand-soft">
                {t("home.showcase.secondaryBadge")}
              </div>
              <p className="mt-2 text-sm">{t("home.showcase.secondaryBody")}</p>
            </article>
          </div>
        </div>
      </section>

      <section className="grid gap-4 rounded-lg border border-border bg-surface p-6 sm:grid-cols-3">
        <ValuePill title={t("home.value.students.title")} body={t("home.value.students.body")} />
        <ValuePill title={t("home.value.companies.title")} body={t("home.value.companies.body")} />
        <ValuePill title={t("home.value.platform.title")} body={t("home.value.platform.body")} />
      </section>

      <section id="for-students" className="space-y-8">
        <SectionHead
          kicker={t("home.students.kicker")}
          title={t("home.students.title")}
          intro={t("home.students.intro")}
        />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {studentFeatures.map((feature) => (
            <FeatureCard key={feature.title} {...feature} />
          ))}
        </div>
      </section>

      <section id="for-companies" className="space-y-8">
        <SectionHead
          kicker={t("home.companies.kicker")}
          title={t("home.companies.title")}
          intro={t("home.companies.intro")}
        />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {companyFeatures.map((feature) => (
            <FeatureCard key={feature.title} {...feature} />
          ))}
        </div>
      </section>

      <section className="space-y-8">
        <SectionHead
          kicker={t("home.platform.kicker")}
          title={t("home.platform.title")}
          intro={t("home.platform.intro")}
        />
        <div className="grid gap-4 sm:grid-cols-3">
          {platformItems.map((item) => (
            <article key={item.image} className="rounded-lg border border-border bg-surface p-6 text-center">
              <img src={`/images/${item.image}.svg`} alt="" className="mx-auto h-16 w-16" />
              <h3 className="mt-4 font-semibold text-ink">{item.title}</h3>
              <p className="mt-1 text-sm text-ink-soft">{item.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="how-it-works" className="space-y-8">
        <SectionHead kicker={t("home.steps.kicker")} title={t("home.steps.title")} />
        <div className="grid gap-6 sm:grid-cols-3">
          {steps.map((step) => (
            <div key={step.number} className="rounded-lg border border-border bg-surface p-6">
              <span className="text-2xl font-bold text-brand">{step.number}</span>
              <h3 className="mt-2 font-semibold text-ink">{step.title}</h3>
              <p className="mt-1 text-sm text-ink-soft">{step.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-8">
        <SectionHead kicker={t("home.testimonials.kicker")} title={t("home.testimonials.title")} />
        <div className="grid gap-4 sm:grid-cols-2">
          {testimonials.map((testimonial) => (
            <blockquote key={testimonial.author} className="rounded-lg border border-border bg-surface p-6">
              <p className="text-ink-soft">{testimonial.quote}</p>
              <footer className="mt-3 text-sm font-medium text-ink-muted">{testimonial.author}</footer>
            </blockquote>
          ))}
        </div>
        <div className="rounded-lg bg-brand p-10 text-center text-white">
          <h3 className="text-xl font-semibold">{t("home.finalCta.title")}</h3>
          <Link
            to="/register"
            className="mt-4 inline-block rounded-md bg-white px-5 py-2.5 text-sm font-semibold text-brand hover:bg-canvas"
          >
            {t("home.finalCta.button")}
          </Link>
        </div>
      </section>
    </div>
  );
}

function ValuePill({ title, body }: { title: string; body: string }) {
  return (
    <div>
      <strong className="block text-ink">{title}</strong>
      <span className="text-sm text-ink-soft">{body}</span>
    </div>
  );
}

function SectionHead({ kicker, title, intro }: { kicker: string; title: string; intro?: string }) {
  return (
    <div className="max-w-2xl space-y-2">
      <span className="text-sm font-semibold uppercase tracking-wide text-brand">{kicker}</span>
      <h2 className="text-2xl font-bold text-ink">{title}</h2>
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
