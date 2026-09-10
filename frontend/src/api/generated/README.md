Generated from `contract/openapi.json` by `npm run api:types` (TASK-043).
Nothing in this directory is written by hand, and it is excluded from lint for
that reason.

It is committed rather than built on the fly so that `tsc`, Vitest and the Vite
build need nothing but this repository — no Python, no running API. CI keeps it
honest with `npm run api:check`, which regenerates and fails on any difference,
so a hand edit and a stale contract fail the same way.

To change what is here, change the API and regenerate:

```bash
cd backend && python scripts/export_openapi.py -o ../contract/openapi.json
cd ../frontend && npm run api:types
```

Import from `src/api/types.ts`, not from here: it re-exports the aliases the
application uses and is what keeps a generator swap from touching every vertical.
