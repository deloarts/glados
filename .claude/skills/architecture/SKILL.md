---
name: architecture
description: Before changing code, understand where this code belongs in Glados' architecture and don't violate the dependency direction. Load when adding features, moving code, or wiring new components.
---

# Glados architecture

The architecture is documented in `docs/`; read it instead of guessing. `docs/CONTRIBUTING.md`
section 1 has the overview and the diagrams; the rules are in `docs/reference/`:

- `module-boundaries.md`: backend layers and what each may import, where new backend code goes,
  the composition root and request-level wiring, the backend modules and their import
  contracts, frontend layers, barrels (`BARRELED_FEATURES` in `frontend/eslint.config.ts`) and
  routing.
- `recipes.md` section 4: adding a frontend feature module.
- `persistence.md` section 3: the event path (outbox, Redis Streams, SSE) and which event bus to
  use.
- `docs/adr/0001-hexagonal-architecture-async-io.md` and `0002-transactional-outbox-redis-streams.md`
  for the reasons.

## Before you add code

1. Name the layer the code belongs to (frontend: core/shared/features/app; backend:
   domain/application/ports/adapters/infrastructure).
2. If it is a feature, check whether the consumer must go through an `index.ts` barrel.
3. Check that every new import points inward (`features → shared → core`; backend
   `adapters → application → ports → domain`). If it points outward, stop and restructure.
4. Check whether an existing abstraction already covers it (resource-view kit,
   `createCrudApi()`, `ManagementCrudShell`, a domain service).
5. Stop and reconsider on any red flag listed in `docs/reference/module-boundaries.md`
   section 1.

After a structural change (moved file, new cross-layer import, new module) run
`poetry run lint-imports` from `backend/` and `npm run lint:check` from `frontend/`.
