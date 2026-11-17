---
name: frontend
description: Any work in frontend/, or a full-stack Glados change that touches the UI. Load before editing Vue components, the API client, or generated types, and whenever a backend API change needs a matching frontend update.
---

# Glados frontend conventions

Every frontend rule is documented in `docs/reference/` (`docs/CONTRIBUTING.md` sections 1.4 and 4
to 7 explain the concepts). Read the parts that apply before writing code:

- Layers, barrels, routing: `module-boundaries.md` section 5. New feature module: `recipes.md`
  section 4.
- Admin settings tabs: `recipes.md` section 5. Read the existing `AdminSettingsTab*.vue` siblings
  first.
- The Glados look (page bars, buttons, tables, dialogs, settings layout): `design-look.md` and
  the `design` skill.
- PDF reports (`src/shared/reports/`): `recipes.md` section 6.
- Language, style, lint, imports, styling, axios client, API layer, types, permissions,
  stores and the logout reset, OpenVue pitfalls: `frontend-conventions.md`.
- i18n, `check:i18n`, informal German address: `frontend-conventions.md` sections 6 and 7.
  Handbook pages: `handbook-pages.md` (and the `handbook` skill).
- Testing (`mountWithApp`, `flushPromises`, typed `vi.fn()`, no `.p-*` / `.mdi-*` selectors):
  `testing.md` section 2.

After a backend API change, the generated types in `src/core/api/generated/webSchema.ts` go
stale: re-export the snapshots in `backend/` and run `npm run generate:api-types` (it reads the
committed snapshot, no backend needs to run). Never edit `webSchema.ts` by hand.

## What to run

From `frontend/`, before calling a change done:

- `npm run test:unit:run -- <spec paths you wrote or touched>`
- `npm run type-check`, `npm run lint:check`, `npm run check:i18n`, `npm run check:api-types`

`npm run ci` runs all of them, including the full spec run. Never run prettier. If an existing
test looks wrong given your change, say so and ask before touching it.
