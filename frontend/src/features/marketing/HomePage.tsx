import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { Arrow, Button } from "@/components/ui";
import { Band, CardGrid, MarketingCard, SectionHead, type MarketingFeature } from "@/features/marketing/sections";

/**
 * The homepage. The hero is not here: it belongs inside the shell's
 * `<header>`, so it lives in `HomeHero` and `PublicShell` places it.
 *
 * Content is carried over verbatim from the Jinja templates — this vertical
 * moves the presentation layer, not the copy.
 *
 * Every card below is built from literal translation calls rather than a
 * template-literal key: `tools/check-i18n.mjs` only recognises literal keys,
 * on purpose — a computed key is exactly the kind of reference a static
 * checker cannot verify against the catalogue.
 */
export function HomePage() {
  const { t } = useTranslation();

  const studentFeatures: MarketingFeature[] = [
    { icon: "note", title: t("home.students.features.0.title"), body: t("home.students.features.0.body") },
    { icon: "briefcase", title: t("home.students.features.1.title"), body: t("home.students.features.1.body") },
    { icon: "target", title: t("home.students.features.2.title"), body: t("home.students.features.2.body") },
    { icon: "book", title: t("home.students.features.3.title"), body: t("home.students.features.3.body") },
    { icon: "users", title: t("home.students.features.4.title"), body: t("home.students.features.4.body") },
    { icon: "chart", title: t("home.students.features.5.title"), body: t("home.students.features.5.body") },
  ];

  const companyFeatures: MarketingFeature[] = [
    { icon: "graduation", title: t("home.companies.features.0.title"), body: t("home.companies.features.0.body") },
    { icon: "idea", title: t("home.companies.features.1.title"), body: t("home.companies.features.1.body") },
    { icon: "search", title: t("home.companies.features.2.title"), body: t("home.companies.features.2.body") },
    { icon: "trend-up", title: t("home.companies.features.3.title"), body: t("home.companies.features.3.body") },
    { icon: "people", title: t("home.companies.features.4.title"), body: t("home.companies.features.4.body") },
    { icon: "flash", title: t("home.companies.features.5.title"), body: t("home.companies.features.5.body") },
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

  const valuePills = [
    { title: t("home.value.students.title"), body: t("home.value.students.body") },
    { title: t("home.value.companies.title"), body: t("home.value.companies.body") },
    { title: t("home.value.platform.title"), body: t("home.value.platform.body") },
  ];

  return (
    <>
      <DocumentMeta title={t("home.seoTitle")} description={t("home.seoDescription")} path="/" />

      <Band tone="surface" className="py-6 sm:py-8">
        <ul className="grid gap-3 sm:grid-cols-3">
          {valuePills.map((pill) => (
            <li key={pill.title} className="rounded-lg border border-border bg-surface px-4 py-3">
              <p className="text-label text-ink">{pill.title}</p>
              <p className="mt-0.5 text-caption text-ink-soft">{pill.body}</p>
            </li>
          ))}
        </ul>
      </Band>

      <Band id="for-students" tone="canvas">
        <SectionHead
          kicker={t("home.students.kicker")}
          title={t("home.students.title")}
          intro={t("home.students.intro")}
        />
        <CardGrid>
          {studentFeatures.map((feature) => (
            <MarketingCard key={feature.title} {...feature} />
          ))}
        </CardGrid>
      </Band>

      <Band id="for-companies" tone="tint">
        <SectionHead
          kicker={t("home.companies.kicker")}
          title={t("home.companies.title")}
          intro={t("home.companies.intro")}
        />
        <CardGrid>
          {companyFeatures.map((feature) => (
            <MarketingCard key={feature.title} {...feature} />
          ))}
        </CardGrid>
      </Band>

      <Band id="features" tone="surface">
        <SectionHead
          kicker={t("home.platform.kicker")}
          title={t("home.platform.title")}
          intro={t("home.platform.intro")}
        />
        <CardGrid>
          {platformItems.map((item) => (
            <MarketingCard key={item.image} title={item.title} body={item.body} className="items-start">
              {/* The illustration precedes the heading visually but follows it
                * in source order, so the heading still opens the card for a
                * screen reader. `alt=""` because the title already says it. */}
              <img src={`/images/${item.image}.svg`} alt="" className="order-first mb-4 size-12" />
            </MarketingCard>
          ))}
        </CardGrid>
      </Band>

      <Band id="how-it-works" tone="dark">
        <SectionHead kicker={t("home.steps.kicker")} title={t("home.steps.title")} onDark />
        <ol className="grid gap-5 sm:grid-cols-3">
          {steps.map((step) => (
            <li key={step.number}>
              <MarketingCard onDark className="h-full">
                <span
                  aria-hidden="true"
                  className="mb-4 flex size-9 items-center justify-center rounded-full bg-primary text-body-sm font-semibold text-primary-fg"
                >
                  {step.number}
                </span>
                <h3 className="text-card-title text-white">{step.title}</h3>
                <p className="mt-2 text-body-sm text-white/70">{step.body}</p>
              </MarketingCard>
            </li>
          ))}
        </ol>
      </Band>

      <Band id="testimonials" tone="canvas">
        <SectionHead kicker={t("home.testimonials.kicker")} title={t("home.testimonials.title")} />

        <div className="grid gap-5 sm:grid-cols-2">
          {testimonials.map((testimonial) => (
            <figure
              key={testimonial.author}
              className="rounded-lg border border-border bg-surface p-6 shadow-xs"
            >
              <blockquote className="text-body text-pretty text-ink-soft">{testimonial.quote}</blockquote>
              <figcaption className="mt-4 text-label text-ink">{testimonial.author}</figcaption>
            </figure>
          ))}
        </div>

        <div className="mt-10 rounded-xl border border-primary-muted bg-gradient-to-br from-primary-subtle to-surface p-8 text-center">
          <h3 className="text-section-title text-balance text-ink">{t("home.finalCta.title")}</h3>
          <Link to="/register" className="mt-5 inline-flex">
            <Button size="lg">
              {t("home.finalCta.button")} <Arrow direction="forward" />
            </Button>
          </Link>
        </div>
      </Band>
    </>
  );
}
