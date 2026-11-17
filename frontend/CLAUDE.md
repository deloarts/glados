# Glados Frontend

See the root [CLAUDE.md](../CLAUDE.md) for what to run, the Don't list, and where every rule is
documented.

## Frontend-specific

- Conventions (layers, API layer, stores, styling, OpenVue pitfalls, i18n, admin tabs, handbook,
  testing): [docs/CONTRIBUTING.md](../docs/CONTRIBUTING.md) sections 1.4, 2.4, 2.5 and 4 to 7 for
  the concepts; the rules are in [docs/reference/](../docs/reference/README.md)
  `module-boundaries.md` section 5, `recipes.md` sections 4 and 5, `frontend-conventions.md`,
  `design-look.md`, `handbook-pages.md` and `testing.md`.
- PDF reports built from `src/shared/reports/`: `docs/reference/recipes.md` section 6.
- `src/core/api/generated/webSchema.ts` is generated from the committed web snapshot by
  `npm run generate:api-types`; never edit it by hand. `npm run check:api-types` fails on drift.
- Before calling a frontend change done, run the specs you touched plus `npm run type-check`,
  `npm run lint:check` and `npm run check:i18n`; `npm run ci` runs every gate.
