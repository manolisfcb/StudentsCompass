import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink } from "react-router-dom";

export interface NavItem {
  to: string;
  label: string;
  /** Legacy nav marked a tab active for a whole subtree (`/resources/*`). */
  end?: boolean;
}

export type ShellVariant = "student" | "company" | "marketing";

const LOGO = "/images/Logo_Ready_to_Use.png";

/**
 * The site header, ported from `includes/navbar.html` and
 * `includes/company_header.html`.
 *
 * The classes are the shipped ones (`student-header`, `student-nav`,
 * `nav-btn nav-btn-primary`, `#mobile-menu`) because the styling lives in the
 * ported `style.css` and keys off exactly those names — including the mobile
 * behaviour, where `nav ul` is the off-canvas panel and `.active` opens it.
 * That is why the menu state here toggles a class rather than a Tailwind
 * conditional: the sheet already owns the animation.
 */
export function AppShell({
  variant,
  brandHref,
  nav,
  actions,
  headerExtra,
  children,
}: {
  variant: ShellVariant;
  brandHref: string;
  nav?: readonly NavItem[];
  /** The logout control, or the marketing shell's login/register pair. */
  actions?: ReactNode;
  /**
   * Content rendered inside `<header>`, below the nav. The homepage hero lives
   * there in `home.html` so that one `.marketing-header` gradient covers nav
   * and hero together; painting it on a second element underneath would leave
   * a seam, because the gradient is angled.
   */
  headerExtra?: ReactNode;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const [menuOpen, setMenuOpen] = useState(false);
  const isCompany = variant === "company";
  const isMarketing = variant === "marketing";

  const headerClass = isMarketing ? "marketing-header" : isCompany ? "company-header" : "student-header";
  const navClass = isMarketing ? "marketing-nav" : isCompany ? "company-nav" : "student-nav";
  const brandClass = isMarketing ? "marketing-brand" : isCompany ? "company-brand" : "student-brand";
  const toggleClass = isCompany ? "company-menu-toggle" : "student-menu-toggle";
  const menuId = isCompany ? "company-mobile-menu" : "mobile-menu";

  return (
    <>
      <a href="#main" className="skip-link">
        {t("layout.skipToContent")}
      </a>

      <header className={headerClass}>
        <nav className={navClass} aria-label={t("app.name")}>
          <div className="container">
            <Link to={brandHref} className={brandClass} aria-label={t("app.name")}>
              <img
                src={LOGO}
                alt={t("layout.logoAlt")}
                className={`brand-logo ${isMarketing ? "brand-logo--hero" : "brand-logo--nav"}`}
              />
              {isMarketing ? null : (
                <span className={isCompany ? "company-badge" : "student-badge"}>
                  {isCompany ? t("layout.badge.company") : t("layout.badge.students")}
                </span>
              )}
            </Link>

            <button
              type="button"
              className={`mobile-menu-toggle ${toggleClass}`}
              aria-label={t("layout.toggleNavigation")}
              aria-expanded={menuOpen}
              aria-controls={menuId}
              onClick={() => setMenuOpen((open) => !open)}
            >
              ☰
            </button>

            <ul id={menuId} className={menuOpen ? "active" : undefined}>
              {nav?.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.end ?? false}
                    onClick={() => setMenuOpen(false)}
                    className={({ isActive }) =>
                      [
                        isMarketing ? "" : "nav-btn nav-btn-primary",
                        isActive ? (isMarketing ? "active-link" : "active") : "",
                      ]
                        .filter(Boolean)
                        .join(" ")
                    }
                  >
                    {item.label}
                  </NavLink>
                </li>
              ))}
              {actions}
            </ul>
          </div>
        </nav>
        {headerExtra}
      </header>

      {children}

      {isMarketing ? <PublicFooter /> : <SiteFooter />}
    </>
  );
}

/** The marketing pages' own footer (`home.html`, `about.html`). */
export function PublicFooter() {
  const { t } = useTranslation();
  return (
    <footer className="public-footer">
      <div className="container">
        <p>{t("layout.footer.copyright", { year: new Date().getFullYear() })}</p>
        <ul>
          <li>
            <a href="#privacy">{t("layout.footer.privacy")}</a>
          </li>
          <li>
            <a href="#terms">{t("layout.footer.terms")}</a>
          </li>
        </ul>
      </div>
    </footer>
  );
}

/** `includes/footer.html`. */
export function SiteFooter() {
  const { t } = useTranslation();
  return (
    <footer>
      <div className="container">
        <p>{t("layout.footer.copyright", { year: new Date().getFullYear() })}</p>
        <ul>
          <li>
            <a href="#privacy">{t("layout.footer.privacy")}</a>
          </li>
          <li>
            <a href="#terms">{t("layout.footer.terms")}</a>
          </li>
          <li>
            <a href="#contact">{t("layout.footer.contact")}</a>
          </li>
        </ul>
      </div>
    </footer>
  );
}

/**
 * `includes/sidebar.html`. The icons are the same inline SVGs the template
 * ships: `.sidebar-icon` styles them by class and recolours them on the active
 * row, which an icon font or an emoji could not reproduce.
 */
export function StudentSidebar() {
  const { t } = useTranslation();
  const items: { to: string; label: string; icon: ReactNode; end?: boolean }[] = [
    { to: "/dashboard", label: t("layout.nav.dashboard"), icon: <IconDashboard />, end: true },
    { to: "/profile", label: t("layout.nav.profile"), icon: <IconUser /> },
    { to: "/career-lab", label: t("layout.nav.careerLab"), icon: <IconChart /> },
    { to: "/resources", label: t("layout.nav.resources"), icon: <IconBook /> },
    { to: "/roadmaps", label: t("layout.nav.roadmaps"), icon: <IconMap /> },
    { to: "/community", label: t("layout.nav.community"), icon: <IconUsers /> },
    { to: "/messages", label: t("layout.nav.messages"), icon: <IconMessage /> },
    { to: "/jobs", label: t("layout.nav.jobs"), icon: <IconTarget /> },
  ];

  return (
    <aside className="dashboard-sidebar left">
      <div className="sidebar-menu">
        <h4>{t("layout.sidebar.explore")}</h4>
        <ul>
          {items.map((item) => (
            <li key={item.to}>
              <NavLink to={item.to} end={item.end ?? false} className={({ isActive }) => (isActive ? "active" : "")}>
                {item.icon}
                <span>{item.label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}

function svgProps() {
  return {
    xmlns: "http://www.w3.org/2000/svg",
    width: 24,
    height: 24,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    className: "sidebar-icon",
    "aria-hidden": true,
  };
}

function IconDashboard() {
  return (
    <svg {...svgProps()}>
      <rect x="3" y="3" width="7" height="9" />
      <rect x="14" y="3" width="7" height="5" />
      <rect x="14" y="12" width="7" height="9" />
      <rect x="3" y="16" width="7" height="5" />
    </svg>
  );
}

function IconUser() {
  return (
    <svg {...svgProps()}>
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

function IconChart() {
  return (
    <svg {...svgProps()}>
      <path d="M3 3v18h18" />
      <path d="m19 9-5 5-4-4-3 3" />
      <circle cx="19" cy="9" r="2" />
      <circle cx="10" cy="10" r="2" />
    </svg>
  );
}

function IconBook() {
  return (
    <svg {...svgProps()}>
      <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
      <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
    </svg>
  );
}

function IconMap() {
  return (
    <svg {...svgProps()}>
      <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
      <line x1="8" y1="2" x2="8" y2="18" />
      <line x1="16" y1="6" x2="16" y2="22" />
    </svg>
  );
}

function IconUsers() {
  return (
    <svg {...svgProps()}>
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  );
}

function IconMessage() {
  return (
    <svg {...svgProps()}>
      <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8z" />
    </svg>
  );
}

function IconTarget() {
  return (
    <svg {...svgProps()}>
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="2" />
    </svg>
  );
}
