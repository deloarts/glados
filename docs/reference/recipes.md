# recipes

The full step lists for the common changes: an endpoint, a field, a domain error, a frontend feature module, an admin settings tab and a PDF report. The guide keeps a short version of each in [CONTRIBUTING.md section 2](../CONTRIBUTING.md#2-recipes); work through the list here when you make the change.

- [1 add an endpoint](#1-add-an-endpoint)
- [2 add a field](#2-add-a-field)
  - [2.1 why request, command and response stay separate](#21-why-request-command-and-response-stay-separate)
- [3 add a domain error](#3-add-a-domain-error)
- [4 add a frontend feature module](#4-add-a-frontend-feature-module)
- [5 add an admin settings tab](#5-add-an-admin-settings-tab)
- [6 add a PDF report](#6-add-a-pdf-report)

## 1 add an endpoint

Work from `backend/`, with paths inside the module the operation belongs to (`src/modules/<module>/`, [module-boundaries.md section 4](module-boundaries.md#4-backend-modules)).

1. Write the schema in `adapters/inbound/api/schemas/` as Pydantic v2 models named `*Request` and `*Response`. Response schemas extend `EntityResponse` (Platform's `schemas/base.py`).
2. Write the DTOs in `application/dto/`: a command DTO for the input and a result DTO extending `ResultBase` (Platform's `dto/base.py`).
3. Write the use case in `application/use_cases/<group>/` as one class with `async def execute(self, actor: User, cmd) -> ResultDTO`. The first thing it does is the permission check through the domain rule services ([backend-conventions.md section 2](backend-conventions.md#2-use-cases-auth-and-permissions)).
4. Put the domain logic in `domain/services/` or on the entity. The use case orchestrates and the domain decides.
5. Call the repository through its `I*Repository` port and await it.
6. Map the entity to the result DTO with a mapper in `application/mappers/`.
7. Add the deps factory in the module's `adapters/inbound/api/deps/` package, in the file of its topic. It takes the repositories and services from the `repositories.py` and `services.py` factories next to it, from Platform's `deps/database.py` (session, unit of work, event bus) and from the deps packages of the modules the module depends on. An implementation that lives above the module comes through a binding ([module-boundaries.md section 3](module-boundaries.md#3-composition-root-and-wiring)).
8. Write the endpoint in `adapters/inbound/api/v1/<surface>/endpoints/` as a thin `async def` that takes the use case through `Depends()`, awaits `execute` and returns the response schema. Register a new router in that surface's `router.py` in `src/bootstrap/adapters/inbound/api/v1/`.
9. Re-export the OpenAPI snapshots with `poetry run python scripts/export_openapi.py`, which rewrites `openapi/web-v*.json` and `openapi/pat-v*.json`. The `pat` snapshot is frozen once a release of that minor exists, and changing it needs a minor bump ([releasing-ci.md section 2](releasing-ci.md#2-the-pat-snapshot-check)).
10. Regenerate the frontend types from `frontend/` with `npm run generate:api-types`, which rewrites `src/core/api/generated/webSchema.ts` from the committed web snapshot without a running backend. Never edit that file by hand.

- Steps 9 and 10 run on their own in the `export-openapi` pre-commit hook.
- CI fails on drift through `scripts/check_openapi.py` and `npm run check:api-types`.
- The surfaces are `web` (the frontend's API), `pat` (the personal-access-token API used by the external SolidWorks add-in), `key` (API-key authenticated), `public` (unauthenticated and branding only) and `auth` (the login routes).

## 2 add a field

A new field on an existing entity touches every layer of its module. Work through the list and skip what does not apply.

1. Add it to the domain entity in `domain/entities/`, plus any rule in `domain/services/` that validates it.
2. Add it to the ORM model in `adapters/outbound/persistence/models/*_model.py`.
3. Write the migration ([development-migrations.md section 3](development-migrations.md#3-writing-a-migration)). A new `NOT NULL` column needs a `server_default`.
4. Update the repository's `_orm_to_entity()` and `_entity_to_dict()`, plus filters or sorting if the field is queryable. A new relationship also needs the repository's load-options function ([persistence.md section 1.5](persistence.md#15-relationships-and-load-options)).
5. Update the command and result DTOs and the application mapper.
6. Update the request and response schemas.
7. Update the use cases that create or update the entity.
8. For made, bought or source items, check whether the field is PDM-mapped and must be read-only in the web ([FIELD_OWNERSHIP.md](../FIELD_OWNERSHIP.md), enforced by `item_field_ownership.py`).
9. Re-export both OpenAPI snapshots and regenerate `webSchema.ts` (section 1, steps 9 and 10).
10. Update the frontend: the feature's `types/`, the form and table components, and the i18n keys in the namespace files of both locales ([frontend-conventions.md section 6](frontend-conventions.md#6-i18n)).
11. Write tests: a unit test for any new rule and an integration test that writes and reads the field through the API.

### 2.1 why request, command and response stay separate

- The request schema, the command DTO and the response schema stay three separately written classes, even for simple master data.
- They agree on names, not on behaviour. Requests carry wire validation and defaults (`ge=0`, `pattern`, enum types), commands carry what the use case needs (often a plain `str`), and responses declare every field as required.
- Create and update requests deliberately differ, such as a required `level` on customer update and all-optional printer updates. A shared base would need per-field overrides that hide exactly these differences.
- Deriving a schema from a DTO is unsafe for the API contract. Several responses, such as `SupplierResponse`, are returned on the frozen `pat` surface, so a field added to a shared definition would silently widen that contract.
- Web-only fields go on a web subclass in the endpoint module instead, like the supplier `external_lead_time_days`.
- Adding the field to each class by hand keeps that decision visible in review.

## 3 add a domain error

- Define the class in `domain/errors.py` of the module that raises it, under the section for the part of the domain it belongs to, and inherit the semantic base that says what went wrong. Platform's own errors stay in `backend/src/modules/platform/domain/exceptions.py`, next to the semantic bases.
- An error that several modules raise or catch lives in the lowest of them, or in a module they all depend on when none of them depends on the others, so that each may import it. Other modules import it from the owner's `domain/errors.py`, which is part of the owner's public API ([module-boundaries.md section 4.2](module-boundaries.md#42-public-api-of-a-module)).
- `_STATUS` in `backend/src/modules/platform/adapters/inbound/api/exception_handlers.py` maps each base to its HTTP status. Platform never names another module's error, so a module's error answers with the status of its base.

| Base | Status | Use it when |
| ---- | ------ | ----------- |
| `BadRequestError` | 400 | The request cannot be carried out as asked, usually because an integration is not configured, a setting is invalid or an external system rejected the credentials. |
| `AuthenticationError` | 401 | A token, code or challenge is wrong or expired. |
| `ForbiddenError` | 403 | The caller may not do this. Permission errors inherit `InsufficientPermissionsError`, which is a `ForbiddenError`. |
| `NotFoundError` | 404 | The record or resource does not exist. |
| `ConflictError` | 409 | The request clashes with the current state, such as a duplicate, a released or locked record, a status that no longer allows the change, or a concurrent change. |
| `PayloadTooLargeError` | 413 | An uploaded file exceeds its size limit. |
| `UnsupportedFileTypeError` | 415 | An uploaded file has a type that is not accepted. |
| `InvalidInputError` | 422 | Well formed input breaks a domain rule, such as a quantity, status transition, pattern or required selection. |
| `RateLimitedError` | 429 | The caller has to wait before trying again. |
| `ExternalServiceError` | 502 | An external system answered with an error or a response Glados cannot use. |
| `ServiceUnavailableError` | 503 | A feature or external system the request needs is unavailable right now. |
| `ServiceUnreachableError` | 503 | An external system the request needs could not be reached at all. The handler logs it as an error rather than a warning. |

- The handler looks up the class chain and the most derived mapped class wins, so a new error needs no entry of its own.
- Add an entry to `_STATUS` only when a Platform error must answer with a different status than its base, as `CredentialsUnverifiableError` does. A module error that needs another status inherits the base that gives it.
- An error that inherits `DomainError` directly and has no entry answers 500 with a generic message, and `backend/tests/unit/test_exception_handlers.py` fails unless it is listed there as never reaching an HTTP response.
- The handler answers `{"detail": str(exc), "code": "<ClassName>"}`. Clients and translations match on `code`, never on `detail`, so an error keeps its class name once it has shipped, also when it moves to another module.
- Let the error propagate from the endpoint instead of catching it and raising `HTTPException`, which drops `code`.
- A caller mistake detected in a use case raises a domain error, not a `ValueError` for the endpoint to translate.
- If the raise site of a Platform error already logs it, add the class to `_SELF_LOGGED` in the same file so it is not logged twice.
- `backend/tests/unit/test_exception_handlers.py` imports every module's `domain/errors.py`, so a module error that resolves to no status fails it like a Platform one.

## 4 add a frontend feature module

- Create `src/features/<x>/` with the standard folders (`api/`, `components/`, `composables/`, `stores/`, `types/`, `utils/`, `views/`, `__tests__/`).
- Add an `index.ts` barrel only when another feature needs to import from it. The lint wall picks the barrel up from the folder.
- Add the feature to its context in `CONTEXT_FEATURES` of `src/__tests__/featureContexts.spec.ts` ([module-boundaries.md section 5.3](module-boundaries.md#53-context-direction)).
- Register the route in `src/router/index.ts` with the right `meta` flags and a lazy-loaded view.
- For a list or detail page, start from the resource-view kit and `ManagementCrudShell`. The `catalogue` and `orders` features show how they are used.

## 5 add an admin settings tab

- A tab is a component named `AdminSettingsTab<Name>.vue`.
- A Platform tab lives in `frontend/src/features/admin-settings/components/` and gets an entry in `PLATFORM_TABS` of `AdminSettingsView.vue` with its icon, its `asyncTab()` loader and an `order` that places it in the strip. Platform's own tabs sit at the multiples of ten. Its label is `adminSettings.tabs.<value>`, and the route is `/settings/<value>`.
- A tab whose settings belong to a feature above Platform, or that needs one of its stores, lives in the `components/` folder of that feature. The feature's plugin registers it with `registerAdminSettingsTab` ([module-boundaries.md section 5.4](module-boundaries.md#54-providers-and-registries)) with the same fields and an `order` between its neighbours. The production tab takes 115, between Numbering at 110 and Branding at 120.
- Such a tab reaches the settings store, `useSettingsSave` and `AdminSettingsTabShell` through the `admin-settings` barrel. A new feature plugin is installed in `main.ts` and `test-utils/mountWithApp.ts`.
- Read two or three siblings before writing a new tab and copy their structure. Do not invent a new layout for a tab that fits the existing mold.
- The tab renders inside `AdminSettingsTabShell`, with the `table` prop for table tabs. It puts the save button as a text button in the `#start` slot of a `Toolbar` in the `#controls` slot, disables it without write permission, and reuses the siblings' `Divider` and shared-control patterns. The field layout is in [design-look.md section 7](design-look.md#7-settings-tabs).
- Three table tabs leave the shell. `AdminSettingsTabUsers` renders a `ManagementCrudShell`, and `AdminSettingsTabApiKeys` and `AdminSettingsTabSolidworksPdm` render a `PageLayout` directly.
- Leave the shell only when the tab is a full resource view the shell cannot host: a record list with its own create and edit flow, or a page that opens a side panel next to its content, as the API key documentation panel and the PDM API console do.

## 6 add a PDF report

Reports are PDFs rendered in the browser by the shared module `frontend/src/shared/reports/` ([ADR 0007](../adr/0007-pdf-reports-in-the-browser.md)). The module owns everything a report has in common: the page frame with the company logo and name, the fixed palette that does not follow the app theme, the bundled fonts, PDF/A-2b output, the export dialog with language, options, download and printing, and the print upload. A feature only describes its report.

1. Write a function that returns a `ReportSpec`. It holds the title for the dialog and the file name, the options it offers as checkboxes, the saved record a print belongs to (null to allow downloading only), and `build(context)`, which returns the report's kind, title, details, body and, for a saved record, its `identity` (public id and a readable reference). Keep the code in the feature, next to what it reports.
2. Build the body from the blocks the module exports (`section`, `keyValueGrid`, `dataTable`, `cell`, `noteCell`, `notice`, `paragraph`, `span`, `list`, `formula`, `group`, `twoColumns`, `drawing` and others) with `context.t`, `context.date`, `context.dateTime` and `context.time`, never with the app's own `t` or date formatting, so the report follows the language chosen in the dialog. `list` takes bulleted or numbered entries that may nest lists of their own, for written notes. `context.sameDay` says whether two instants fall on the same day in the tenant's timezone, so a period within one day prints its date once.
3. Style by name only. Text and cells take a named style from `shared/reports/utils/styles.ts` (`emphasis`, `italic`, `muted`, `note`, `alert`, `cellMarked` and others), and blocks take a spacing preset (`tight`, `before`, `after` and others). When a report needs a look that no style gives, add the style to the engine so every report can use it.
4. Draw charts as SVG strings coloured with `DRAWING_COLORS`. A drawing the app already shows as an SVG component goes in through `renderComponentSvg`. Photos go through `loadReportImage`, which shrinks them to the size they are printed at. An image the page already holds as a blob goes through `reportImageFromBlob`, whose `maxHeight` and optional `maxWidth` bound it in both directions, so a wide screenshot is scaled down too.
5. On the page, call `useReportExport()`, render `<ReportExportDialog v-model:visible="visible" :report="report" />` once, and call `open(spec)` from the Print button. A tool only adds a `report` loader, and `reportOptions` if it has any, to its entry in `features/tools/registry.ts`, and `utils/toolReport.ts` turns it into a spec.
6. To make the report printable, add a value to `UploadedPrintDocument` (`print_classifier.py`), a branch with the record's visibility check, lineage and revision in `application/services/uploaded_document_roots.py`, and a label under `reports.classifiers` in both locales. The same branch lets the export journal record every download and print of the record, which the shared `ReportDistribution` component lists.
7. Test the spec's content with `createReportContext`, and render it once with `renderPdfForTest` from `src/test-utils`, which proves that pdfmake accepts the document and that it is PDF/A-2b.

- The identity puts a QR code on every page that opens exactly that revision through `/resolve/{public_id}`, with the reference and a line marking the page as a copy next to it.
- A builder never writes font sizes, colours, fonts, margins or pdfmake nodes, and never imports pdfmake. ESLint enforces both for files named `*report*` in a feature.
- There is no browser print. A page never relies on `window.print()` or on print style sheets.
- A record with a distribution of its own may print and download through its own routes and dialog instead of the shared ones. Meeting notes do: `MeetingPrintDialog` builds the PDF, and the meeting's print, download and send routes check the cards the PDF was built from, compute its checksum, journal it and keep a snapshot of what it contained. The general print and download routes refuse the `meeting_notes` document, so no meeting PDF reaches the journal without its snapshot.
