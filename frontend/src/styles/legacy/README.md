# Legacy stylesheets

These files are the production design system of the Jinja app
(`backend/app/static/css/`), ported so the React rewrite renders the same UI
rather than a second one.

- `base.css` — `style.css` verbatim: the shell (header, nav, sidebar, footer),
  the auth screens, the marketing pages and the shared card/button vocabulary.
- `pages/<name>.css` — the sheet that page loaded, with every selector prefixed
  by `.pg-<name>`.

The prefix is not cosmetic. Each sheet used to be the only page sheet on the
document, so `.stat-card` means one thing in `dashboard.css` and another in
`company-dashboard.css`, and `.tag` means four things. A bundler puts all of
them on every route, so each route renders its wrapper with the matching
`pg-` class (see `src/components/layout/PageScope.tsx`) and the sheets stay
apart. `@keyframes` are renamed per scope for the same reason (`fadeIn` exists
three times with three definitions).

To re-port after a change to the Jinja sheets, re-run the port rather than
editing here by hand:

    python3 tools/port-legacy-css.py
