# Legacy stylesheets

What is left of the design system ported out of the Jinja app
(`backend/app/static/css/`). It used to be nineteen sheets and ~14,800 lines
covering the whole product; it is now two files serving the marketing site.

- `base.css` — the marketing pages' layout and components: the home hero, the
  feature/testimonial/step sections, the About page's problem, ROI, framework
  and philosophy blocks, and the reference modal.
- `pages/about.css` — the handful of About-only rules that sheet carried.

## Why these two stay

Every screen behind a login is on the design system in `src/components/ui`.
These two are not, and deliberately so: they are bespoke landing-page layouts —
each section is laid out once and reused nowhere — so turning them into
components would produce a set of one-use abstractions rather than a shared
vocabulary. The cost of leaving them is one stylesheet; the cost of migrating
them is the same markup expressed twice as long, with a real risk of quietly
changing the page the product is sold on.

They are not, however, a second source of truth for colour. Every brand,
surface, text and border value in them is a `var(--color-*)` reference into
`styles/theme.css`, so changing the brand teal still reaches the marketing
site. What remains hardcoded is a small number of one-off decorative tints
that appear once each — naming those as tokens would grow the system, not
centralise it.

## Scoping

The `.pg-<name>` prefixes and the `PageScope` component they needed are gone
with the per-page sheets. `base.css`'s bare element selectors — `header`,
`nav`, `main`, `section`, `h2`, `footer` — are scoped under `.marketing-page`,
which `PublicShell` renders. Unscoped they applied to every one of those
elements in the whole app: `header` painted a teal gradient over every
`PageHeader`, and `main { padding: 4rem 0 }` spaced every screen like a
landing page.

## Cascade

`styles/index.css` imports this into a `legacy` layer that sits between
Tailwind's `base` and `components`, so any utility class outranks anything
here. That is what allows a marketing page to be migrated later without first
deleting the rules it is replacing.

## If you change the Jinja sheets

Don't re-port. The port tooling is gone and these files have diverged: dead
rules pruned, colours tokenised, selectors scoped. Edit them here.
