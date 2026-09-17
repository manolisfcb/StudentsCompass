import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

/**
 * The homepage hero. It lives in `<header class="marketing-header">` rather
 * than in `<main>` because that is where `home.html` puts it: the header's
 * angled gradient runs behind nav and hero as one surface, and splitting them
 * onto two elements would restart the gradient halfway down.
 *
 * `PublicShell` passes it to `AppShell` as `headerExtra` on `/` only.
 */
export function HomeHero() {
  const { t } = useTranslation();
  return (
    <div className="hero hero-home">
      <div className="container">
        <div className="hero-grid">
          <div className="hero-copy">
            <span className="hero-kicker">{t("home.hero.kicker")}</span>
            <h2>{t("home.hero.title")}</h2>
            <p>{t("home.hero.body")}</p>
            <div className="hero-actions">
              <Link to="/register" className="cta-button">
                {t("home.hero.primaryCta")}
              </Link>
              <Link to="/about" className="hero-secondary-link">
                {t("home.hero.secondaryCta")}
              </Link>
            </div>
            <div className="hero-proof-list">
              <span>{t("home.hero.proof1")}</span>
              <span>{t("home.hero.proof2")}</span>
              <span>{t("home.hero.proof3")}</span>
            </div>
          </div>

          <div className="hero-visual">
            <article className="hero-showcase hero-showcase-primary">
              <div className="hero-showcase-label">{t("home.showcase.primaryLabel")}</div>
              <h3>{t("home.showcase.primaryTitle")}</h3>
              <p>{t("home.showcase.primaryBody")}</p>
              <div className="hero-mini-stats">
                <div>
                  <strong>{t("home.showcase.stat1Title")}</strong>
                  <span>{t("home.showcase.stat1Body")}</span>
                </div>
                <div>
                  <strong>{t("home.showcase.stat2Title")}</strong>
                  <span>{t("home.showcase.stat2Body")}</span>
                </div>
                <div>
                  <strong>{t("home.showcase.stat3Title")}</strong>
                  <span>{t("home.showcase.stat3Body")}</span>
                </div>
              </div>
            </article>
            <article className="hero-showcase hero-showcase-secondary">
              <div className="hero-showcase-badge">{t("home.showcase.secondaryBadge")}</div>
              <p>{t("home.showcase.secondaryBody")}</p>
            </article>
          </div>
        </div>
      </div>
    </div>
  );
}
