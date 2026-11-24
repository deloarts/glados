# module boundaries

The exact rules for where code lives and what it may import, in the backend layers and modules and in the frontend features. The concept, with the diagrams of the contexts and of one write, is in [CONTRIBUTING.md section 1](../CONTRIBUTING.md#1-architecture-in-one-page).

- [1 backend layers](#1-backend-layers)
- [2 where new backend code goes](#2-where-new-backend-code-goes)
- [3 composition root and wiring](#3-composition-root-and-wiring)
- [4 backend modules](#4-backend-modules)
  - [4.1 dependency order](#41-dependency-order)
  - [4.2 public API of a module](#42-public-api-of-a-module)
  - [4.3 import contracts](#43-import-contracts)
  - [4.4 reaching across modules](#44-reaching-across-modules)
  - [4.5 registrations and settings](#45-registrations-and-settings)
  - [4.6 use-case layers inside Planning and fulfillment](#46-use-case-layers-inside-planning-and-fulfillment)
- [5 frontend layers](#5-frontend-layers)
  - [5.1 the feature wall](#51-the-feature-wall)
  - [5.2 import cycles](#52-import-cycles)
  - [5.3 context direction](#53-context-direction)
  - [5.4 providers and registries](#54-providers-and-registries)
  - [5.5 composing higher contexts](#55-composing-higher-contexts)
  - [5.6 placement and routes](#56-placement-and-routes)

## 1 backend layers

Inside a module under `src/modules/<module>/`, dependencies point inward only: adapters, then application, then ports, then domain. Infrastructure is cross-cutting and may be imported by adapters.

| Layer | Path in a module | Holds | May import |
| ----- | ---------------- | ----- | ---------- |
| domain | `domain/` | Entities (plain dataclasses whose base has `id` and `public_id`), rule and policy services, value objects, events and the module's domain errors in `errors.py`. Platform holds the semantic error bases and its own errors in `exceptions.py`. | The domain of its own module and of the modules it depends on, and the shared kernel. It never imports FastAPI, SQLAlchemy, Pydantic or Redis, and it is sync code that never awaits. |
| application | `application/` | One use case class per action under `use_cases/<group>/`, DTOs, entity to DTO mappers and application services. | Domain, ports, and Platform's `infrastructure.logging` and `infrastructure.security`. |
| ports | `ports/outbound/` | Repository Protocols (`I*Repository`) and service ports such as mail, printer, LDAP, event bus, webhooks, storage and unit of work. | Domain. |
| adapters | `adapters/` | FastAPI routes and schemas under `inbound/api/`, models, repositories and mappers under `outbound/persistence/`, external clients under `outbound/external/`, and `outbound/rendering/`. | Everything inward. |
| infrastructure | `infrastructure/` in Platform and a few other modules | Settings, the event relay, workers and live subscriber, logging, security and the Redis client. | No contract limits it. |

- The application layer imports Platform's `infrastructure.security` for the hashing, API key and PAT generation, RFID lookup and time-tracking fingerprint helpers that live there. No import-linter contract limits which infrastructure modules it may import, so keep it to logging and security.
- `poetry run lint-imports` enforces the layers inside every module and across modules, keeps FastAPI, Starlette and SQLAlchemy out of the application and ports layers, and checks the module boundaries of section 4 through the contracts in `backend/.importlinter`. It runs as a pre-commit hook and in CI.
- `backend/tests/unit/test_architecture.py` adds a few checks import-linter cannot express.
- A request flows through an async endpoint, the request schema, a command DTO, `await UseCase.execute(actor, cmd)`, sync domain services and entities, an awaited repository port, a mapper, the result DTO and the response schema.

Red flags in review:

- An ORM model from `adapters/outbound/persistence/models/` is imported outside the persistence adapters.
- A use case imports anything from FastAPI or Starlette.
- An endpoint holds business logic instead of one use case call and a response mapping.
- A concrete adapter, repository or service is instantiated anywhere except `src/bootstrap/`, a module's `adapters/inbound/api/deps/` package or the read tier's `adapters/inbound/api/deps.py`.
- A module imports `src/bootstrap/`.

## 2 where new backend code goes

Pick the module first (section 4), then the layer inside it. Paths are relative to `src/modules/<module>/`.

- A business rule goes into `domain/services/`, or onto the entity when it only guards that entity's own invariants.
- A persisted concept needs a domain entity in `domain/entities/`, a port in `ports/outbound/repositories/`, an ORM model in `adapters/outbound/persistence/models/`, a repository in `adapters/outbound/persistence/repositories/` and a migration ([development-migrations.md section 3](development-migrations.md#3-writing-a-migration)).
- A new API operation follows [recipes.md section 1](recipes.md#1-add-an-endpoint).
- A new external system such as a mail provider, printer protocol or webhook target gets a port in `ports/outbound/` and an adapter in `adapters/outbound/`, and is wired in a factory of the module's `adapters/inbound/api/deps/` package, or in `src/bootstrap/` when a background job needs it.
- A new ORM model needs no registration, because `alembic_imports.py` walks the models package of every module.

## 3 composition root and wiring

- `backend/src/bootstrap/main.py` is the only composition root.
- Its lifespan runs the migrations, seeds the system user, and starts the DB log handler, the backup and PDM poll schedulers, the notification digest loop, the Redis Streams event workers (notifications, webhooks, auto print, PDM sync), the live row sync and the outbox relay.
- Every background job is an asyncio task on the worker process's event loop. Schedulers are interval tasks (`run_every` in `src/modules/platform/infrastructure/interval_task.py`), never threads.
- When only one of the gunicorn workers may act on a tick, a Postgres advisory lock decides which one.
- Each module builds its use cases in its own `adapters/inbound/api/deps/` package, one file per topic, such as `items.py` or `orders.py`, next to `repositories.py` (one factory per repository on the request's session, and the module's settings store) and `services.py` (adapters and process-wide services such as the rate limiters).
- Platform's `deps/database.py` provides the session (`get_db`), the unit of work, the transactional event bus and the public id resolver, which every module's factories use.
- A factory may use the factories of the modules its module depends on, such as a repository of Catalogue or a facade from Catalogue's `deps/facades.py`. It types such a parameter with the port the use case declares, a query port or a facade, never with another module's repository port.
- Where a factory needs an implementation from a module above its own, from the read tier or from the root, the module declares a `Binding` (Platform's `deps/binding.py`) and a dependency that reads it in its `deps/bindings.py`, such as Catalogue's `get_cad_source` or Platform's `get_schedule_recompute`. `src/bootstrap/bindings.py` binds each one at startup with a builder on the request's session, and `register_all` runs it in every process.
- A binding holds a plain builder, not a FastAPI dependency, because FastAPI reads a dependency's parameters when the route is declared, before the root could name the implementation. The dependency that reads the binding declares what the builder needs, usually only the session. The production app never uses `app.dependency_overrides`, which tests keep for replacing a dependency: once that mapping is not empty, FastAPI rebuilds every dependency of every request.
- A test replaces a bound implementation by overriding the module's dependency, such as `get_schedule_recompute_generation_counter` in Platform's `deps/bindings.py`, which every module's walk request shares.
- The read tier's factories are in `src/read/adapters/inbound/api/deps.py`. The whole settings record (`get_admin_settings_repo`) is bound there by the root, since its store extends the stores of every module.
- Endpoints receive use cases through `Depends()` and never construct a use case or repository themselves.

## 4 backend modules

### 4.1 dependency order

- There are seven modules under `backend/src/modules/` ([ADR 0012](../adr/0012-modular-monolith-bounded-contexts.md)), read from the bottom: `platform`, then `catalogue`, then `workspace` and `external_data` (CAD and external data), which both build on Catalogue, then `fulfillment` (Planning and fulfillment), which builds on Workspace, then `quality` (Quality and documents) and `operations`, which build on Planning and fulfillment.
- Each module declares the modules it may import in `DEPENDS_ON` in `backend/tests/unit/test_context_boundaries.py`.
- Quality and documents and Operations are siblings and never import each other.
- The declared graph has no cycles, and a declared dependency that no import uses fails the test, so the list says what the code does.
- `src/shared_kernel/` sits below every module. It holds code without business meaning, such as the clock, changelog entries, the base classes and the lifecycle action names. Every module may import it, and it imports nothing else.
- `src/read/` sits above the modules and holds readers that span every module, such as global search, the settings overview, the metrics collector and the infoscreen feed. It may import every module, but only through its public API (section 4.2).
- `src/bootstrap/` is the composition root and wires every module. It holds `main.py`, the CLI, the API routers, `registrations.py`, `bindings.py` and the background workers that wire use cases of several modules, such as `workers/pdm_schedule.py`.
- No module imports the read tier, and neither a module, the shared kernel nor the read tier imports the composition root.

### 4.2 public API of a module

- A module reaches another module only through its public API.
- The public API is the module's `api.py`, which re-exports the ports it owns for other modules to implement or extend, plus its named interfaces.
- The named interfaces are its domain entities (`domain/entities/`), events (`domain/events/`), value objects (`domain/value_objects/`) and errors (`domain/errors.py`), the rules other modules apply (`domain/policies/`), its DTOs (`application/dto/`) and the mappers that produce them (`application/mappers/`), its query facades (`application/facade/`), its ports outside `ports/outbound/repositories/`, and its settings store, which the stores of the modules above it extend.
- The ports outside the repositories include the narrow query ports other modules read through (`ports/outbound/<module>_queries.py`), which the module's repositories satisfy as they are.
- Platform, the technical base, also publishes its entities, domain services, application services, infrastructure and persistence helpers, and the generic settings store every module's store extends. Its use cases, web routes and other repositories stay internal.
- A module's dependency factories (`adapters/inbound/api/deps/`) are public only to the factories of the modules above it, which wire its repositories and facades into their own use cases, so the routes of another module never take its use cases. Platform's factories, among them the session, the unit of work and the event bus, are public to every module.
- Everything else of a module is internal: its domain and application services, use cases, mappers, repository ports and adapters.
- Other modules read a module's entities but change them only through its use cases.
- Two adapter packages are public to the same layer of other modules. Because of the shared database, other modules' persistence adapters may use a module's ORM models and row mappers (`adapters/outbound/persistence/models/` and `mappers/`) to join and map. Other modules' routes may embed its API schemas (`adapters/inbound/api/schemas/`) in their responses.
- The read tier is held to the same public API as a module. Its persistence adapters (`src/read/adapters/outbound/persistence/`) may use the ORM models of every module for their read queries, and its inbound adapters (`src/read/adapters/inbound/`) may embed the API schemas. It never imports a module's use cases, application or domain services (Platform's excepted), repository ports, repositories, external adapters, web routes or infrastructure (Platform's excepted).
- A reader in the read tier that needs a piece of a module beyond its public API gets it published by the module: a narrow query port in `ports/outbound/<module>_queries.py` for a repository read, a policy in `domain/policies/` for a rule or table, such as the lifecycle tables of Planning and fulfillment in `domain/policies/lifecycle.py`, or a query facade in `application/facade/` for an application service. A piece only the read tier uses moves into the read tier, as the infoscreen feed rules did.

### 4.3 import contracts

- `backend/.importlinter` checks section 4 with `poetry run lint-imports`.
- Each module has one `forbidden` contract for the modules it does not declare, one `protected` contract for its internals, one for its ORM models and row mappers and one for its API schemas. Each module but Platform also has a `protected` contract for its `adapters/inbound/api/deps/` package, which only the deps packages of other modules and the root may import, so another module's route never takes a module's use case. Further contracts cover the kernel, the read tier, the composition root, which nothing in `src/modules/`, `src/shared_kernel/` or `src/read/` may import even indirectly, and the use-case layers inside Planning and fulfillment (section 4.6).
- The privacy contracts name no allowed importer outside the module and the composition root, so they hold the read tier to the public API too. The models contracts allow the read tier's persistence adapters and the schemas contracts its inbound adapters.
- The `read-tier-public-api` contract forbids the read tier the internal packages of every module, listed in section 4.2, so a new internal package is covered before any privacy contract names it.
- The test in `test_context_boundaries.py` keeps the dependency contracts in step with `DEPENDS_ON`.
- A contract may list an exception in `ignore_imports` with its reason while a fix is under way. An entry that matches no import fails the run, so the fix also removes its line. No contract lists an exception today.
- A module whose privacy contract ignores no import of another module is drawn with a thick border in the context diagram of the guide.

### 4.4 reaching across modules

- To reach a higher module, go through a port the lower module owns and the higher one implements, or through a domain event.
- To reach a lower module's internals, go through its `api.py`, adding what is missing there, or through a named interface.
- The project work ports show the port pattern. Workspace owns `ports/outbound/project_work_port.py` (the live work and summary of a project, and what a project update does to its work) and publishes it in `workspace/api.py`. Planning and fulfillment implements it (`project_work_repository.py`, `project_work_propagation.py`), and the composition root binds its implementations to Workspace's `deps/bindings.py`.
- The schedule walk works the same way. Code below Planning and fulfillment that changes what the schedule depends on runs `recompute_schedule_after_commit` from Platform's `application/services/schedule_recompute_port.py`, and the root binds the walk to Platform's `get_schedule_recompute`.
- Writes into another module go through its command facades, such as Catalogue's `application/facade/item_commands.py`, which publishes the item commands PDM ingest drives.
- Where a module owns the data it writes by design, it writes through a store port the lower module publishes. CAD and external data saves the CAD rows it owns ([FIELD_OWNERSHIP.md](../FIELD_OWNERSHIP.md)) through Catalogue's `ports/outbound/cad_item_store_port.py`.
- Catalogue's CAD source port is the same shape from the other side. Catalogue's item use cases ask `ports/outbound/cad_source_port.py` for the CAD policy (whether a CAD source is connected and whether its rows are read-only), and CAD and external data answers it from the PDM settings in `PdmCadSource`. Item code therefore never reads the PDM settings, and a second CAD source is a second implementation.

### 4.5 registrations and settings

- Platform never names a module. Code that serves every module takes each module's part from `src/bootstrap/registrations.py`, which every process entry point (the app factory, the CLI, the test session) runs once.
- The registrations cover the event types the event bus carries (`register_events`), the models a scanned public id may name (`register_public_id_models`), the live-sync topics of each model (`register_live_topics`) and the notification rules (`register_notification_rules`).
- Notification rules live next to the use cases whose events they read, such as `use_cases/order/notifications.py`, and take Platform's `NotificationSender` from `application/services/notification_rules.py`.
- A new event, live resource or notification is registered there by its module.
- Platform's own settings sections are in `IPlatformSettingsRepository`. Each module extends it with its own sections in its settings port, which lives in the module's `ports/outbound/` and `api.py` and is implemented by its settings store next to the module's other repositories.
- A use case types its settings dependency with its own module's port, so it sees its own sections and those of the modules below it.
- `IAdminSettingsRepository` and `SqlAlchemyAdminSettingsRepository` are the whole record, for the read tier and the composition root.
- The ORM models of every module are loaded by Platform's `alembic_imports.py`, which finds the models packages on disk.

### 4.6 use-case layers inside Planning and fulfillment

Planning and fulfillment stays one module because the lifecycle reconciler locks demands, orders and lots in one transaction ([ADR 0012](../adr/0012-modular-monolith-bounded-contexts.md)). Its use-case groups under `application/use_cases/` are layered inside it instead, and the `fulfillment-use-case-layers` contract in `backend/.importlinter` checks the layering. A group may import the groups in the layers below it, never one above it, and the groups that share a layer never import each other.

| Layer, from the top | Groups | Why it sits there |
| ------------------- | ------ | ----------------- |
| composition | `dashboard`, `todo`, `external_work` | The todo list composes the list use cases of the groups below and adds the user's open meeting todos through Workspace's `IMeetingTodoQueries` port, and the dashboard reads their repositories. The list of external work reads the lots and the scheduling services and is imported by no other group, only by its facade. |
| award and allocation | `quote_request`, `source_item_allocation` | Awarding a quote request creates an order with its lines and assigns lot positions to it. The source item allocations reuse the source item demand family's binding (`source_item_demand/_spec.py`). |
| work | `order`, `bought_item_demand`, `made_item_demand`, `source_item_demand`, the three `*_demand_bucket` groups, `production_order`, `production_machine`, `machine_pool`, `admin_settings` | Each group owns one kind of record. An order delivery of a made line and a production order's completion or scrap create a lot, and cancelling a demand cancels its lot, so these groups sit above the lots. |
| lots | `production_lot` | Of the other groups, the lot use cases import only the schedule recompute. |
| scheduling and the demand family | `production_schedule`, `_demand_family` | The machine schedule recompute every plan-changing write runs, and the demand use cases the three demand kinds share through their spec. |
| services | `application/services/` | The lifecycle reconciler and loader, the lock helpers and the other shared services. The `services` contract also forbids them every use case. |

- A helper only one group uses stays in that group as a private module, such as `order/_lines.py` or `production_order/_locks.py`. A helper a second group needs moves into `application/services/`, which may import no use case.
- A use case that serves another group's route stays in the group whose layer allows its imports. `ScrapLotPieces` serves the lot scrap route but sits in `production_order/` because it delegates to `ScrapProductionPieces`, which creates the replacement lot.
- A new use-case group takes its place in the contract before it imports or is imported by another group; `backend/tests/unit/test_context_boundaries.py` fails while a group is missing from it.
- The contract lists no ignored imports. A call that would point upwards is moved into a service or the group is placed higher, never ignored.

## 5 frontend layers

`frontend/src/` is layered `core`, then `shared`, then `features`.

| Layer | Holds | May import |
| ----- | ----- | ---------- |
| `core/` | Platform code only and nothing feature-specific, such as the axios client (`core/api/index.ts`), the generated types (`core/api/generated/webSchema.ts`), auth and the permissions enum (`core/auth/permissions.ts`), the singleton stores (current user, layout, connection, host, loading bar), i18n, the realtime SSE client (`core/realtime/`) and shared composables such as `useSequencedFetch` and `useServerTable`. | Nothing above it. |
| `shared/` | Cross-feature UI and logic, such as the resource-view kit (`PageLayout`, `InfoBar`, `ControlsBar`, `ViewsBar`), `ManagementCrudShell`, handlers, demand import, help (`shared/help`), the registries of the admin settings tabs and the account page (`shared/admin-settings-tabs`, `shared/account-page`), the supplier mail templates (`shared/order-mail`) and the API factories for routes several item kinds share. | `core`. |
| `features/<name>/` | One domain module each, with `api/`, `components/`, `composables/`, `stores/`, `types/`, `utils/`, `views/`, `__tests__/` and an optional `index.ts` barrel. | `core`, `shared`, and features of its own context or a declared one, only through their barrel. |
| `app/layouts/` | App shells, header, sidebar and banners. | |

- No file in `core/` or `shared/` imports a feature directly, although `core/stores/currentUserStore.ts` imports the router, which imports feature views.
- Three checks guard the layers: the feature wall in `frontend/eslint.config.ts` (`no-restricted-imports`) and the two specs of sections 5.2 and 5.3.

### 5.1 the feature wall

- Every feature with an `index.ts` barrel is behind the wall. `BARRELED_FEATURES` in `eslint.config.ts` reads them from the folders.
- Another feature imports a walled feature only through `@/features/<x>/index.ts`. A deep import from one feature into another fails lint.
- The rule covers static imports in files under `src/features/` only. A lazy `import()` of another feature's view, such as the catalogue tabs or the QA tab of the production view, is not checked.
- The same wall covers `src/router/`, `src/app/` and `App.vue`.
- `App.vue` deep-imports one production composable under an `eslint-disable-next-line` with its reason, so the production barrel stays out of the entry chunk, and `app/layouts/AppLayout.vue` lazily loads the lot detail and scan dialogs by path. Do not add more of either.

### 5.2 import cycles

`src/__tests__/featureImportCycles.spec.ts` builds the import graph of `src/`, leaving out specs and test helpers, and fails on two kinds of cycle.

- A module cycle that spans two features fails, and there is no allowlist for it. A barrel re-exports components, so importing it evaluates everything behind it, and a module reached from one barrel that imports a second barrel leading back to the first makes evaluation order depend on which feature loads first.
- Break a module cycle by moving the shared piece to `shared/` or to the feature that owns it, by dropping a barrel export no other feature uses, or, for a dialog opened on demand, by loading it with `defineAsyncComponent`.
- A feature-level cycle, counting every import including `import type`, fails unless the spec's allowlist names it. Pairs that import each other would be listed in `ALLOWED_MUTUAL_IMPORTS`, and single-direction edges that close a longer cycle in `ALLOWED_CYCLIC_EDGES`, each with a one-line reason.
- Both allowlists are empty, so any new feature-level cycle fails.

### 5.3 context direction

- `src/__tests__/featureContexts.spec.ts` puts every feature in one of the backend's contexts or in the read tier (section 4.1) and checks the direction on the same import graph.
- A feature imports features of its own context or of a context in `DEPENDS_ON`.
- The read tier holds cross-context readers and the pages that compose several contexts. It may import any context and is imported by none.
- Exceptions would be listed in `UPWARD_IMPORTS` with their reasons. An entry that no longer matches an import fails, so the list only shrinks, and it is empty.
- To reach a higher context, let the page that hosts both compose them, let the higher feature register its part with the lower page (section 5.4), or notify through `core/realtime` or a store event.
- The spec also keeps `core/` and `shared/` free of feature imports.

### 5.4 providers and registries

- Features show help through `@/shared/help` and start label and docket prints through `usePrint()` from `@/shared/print`.
- `main.ts` installs the handbook and the print templates (`templatePrinting` from `print-labels`) as the providers, and `test-utils/mountWithApp.ts` installs both for specs.
- No feature imports the handbook or the printing features to show help or to print.
- The Platform pages that host parts of higher contexts collect them the same way, as the backend does when each module registers its part at startup.
- A feature registers its admin settings tab with `registerAdminSettingsTab` from `@/shared/admin-settings-tabs`, and its account tab or My Account section with `registerAccountTab` or `registerAccountSection` from `@/shared/account-page`.
- The registration runs inside a plugin that `main.ts` and `test-utils/mountWithApp.ts` install, such as `timeTrackingSections` (the Time Tracking account tab, the credentials section and the time tracking settings tab), `productionSettingsTab` in `production` and `edpSettingsTab` in `bought-items`, beside the EPLAN Data Portal lookup.
- Both installers import each plugin module by path, so the feature's barrel stays out of the entry chunk.
- The pages render the registered entries beside their own by order and never import the features.

### 5.5 composing higher contexts

Where a lower screen needs content of a higher context, the page above both supplies it.

- The catalogue item detail pages are the read-tier `catalogue` feature and compose orders, lots and project usage directly.
- The read-tier `catalogue-section` provides the order and lot dialogs the item catalogues open from a row, through the injection keys `boughtItemOrderDialogsKey` and `madeItemLotDialogsKey` that the item features declare.
- The product page and the sequence page pass the device dialog its calculations section as a slot, and the product page passes the devices tab the calculation count per device as a prop.
- A management screen that picks records of another feature can live apart from the master data it manages. `fabrication-method-management` picks suppliers while suppliers read `fabrication-methods`, and the read-tier `inspection-method-management` picks QA machines.

### 5.6 placement and routes

- The demand screens belong to Planning and fulfillment. The bought-item demands are in `procurement`, and the made-item and source-item demands in `production`.
- The item features keep the demand API and types, because `projects` in Workspace reads them too.
- `features/production/` keeps shared code at its root and splits its screens into one subfolder each, each holding only the folders it needs.
- Routes live in `src/router/index.ts`, lazy-load their view and declare `meta` flags (`requiresAuth`, `layout`, `requiresAdmin`, `requiresProductionPlanning`, and `phone` for what a phone offers, [design-look.md section 11](design-look.md#11-phone-layout)).
