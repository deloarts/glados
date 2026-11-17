# Glados Backend

See the root [CLAUDE.md](../CLAUDE.md) for what to run, the Don't list, and where every rule is
documented.

## Backend-specific

- Conventions: [docs/CONTRIBUTING.md](../docs/CONTRIBUTING.md) sections 1 to 3 and 7 for the
  concepts; the rules are in [docs/reference/](../docs/reference/README.md)
  `module-boundaries.md`, `backend-conventions.md`, `persistence.md`, `lifecycle.md` and
  `testing.md`. Migrations, tests and async rules: `development-migrations.md`,
  `development-testing.md` and `development-async.md` in the same folder.
- OpenAPI snapshots in `openapi/` (`pat-v*.json` frozen per released minor, `web-v*.json` free
  to change) are written by `scripts/export_openapi.py` and gated by `scripts/check_openapi.py`;
  see [docs/reference/releasing-ci.md section 2](../docs/reference/releasing-ci.md#2-the-pat-snapshot-check). After changing a
  web route or schema, re-export and run `npm run generate:api-types` in `frontend/`. Never
  change the `pat` snapshot of a released minor without telling the user it needs a minor bump.
- Version bumps go through `scripts/bump_version.sh X.Y.Z` at the repo root, never by editing
  one of the version files alone ([docs/RELEASING.md section 1](../docs/RELEASING.md#1-versioning-policy)).
