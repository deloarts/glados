# frontend conventions

The rules for frontend code: code style, styling, promises, API calls and types, i18n and German copy, stores and live updates, and the OpenVue pitfalls. The concept is in [CONTRIBUTING.md sections 4 and 5](../CONTRIBUTING.md#4-frontend-conventions). How a page looks is in [design-look.md](design-look.md), and the frontend layers and feature walls in [module-boundaries.md section 5](module-boundaries.md#5-frontend-layers).

- [1 code style](#1-code-style)
- [2 styling](#2-styling)
- [3 promises](#3-promises)
- [4 API calls](#4-api-calls)
- [5 API types and their lint guards](#5-api-types-and-their-lint-guards)
- [6 i18n](#6-i18n)
- [7 German copy and language](#7-german-copy-and-language)
- [8 state and live updates](#8-state-and-live-updates)
- [9 shared components and OpenVue pitfalls](#9-shared-components-and-openvue-pitfalls)

## 1 code style

- Use `<script setup lang="ts">` everywhere.
- TypeScript is strict with `noUncheckedIndexedAccess`, so indexed access may be `undefined`.
- Write single quotes and no semicolons. There is no formatter config, so never run prettier, and match the file you are editing.
- Lint is eslint (`eslint.config.ts`) plus oxlint (`.oxlintrc.json`). `npm run lint` fixes, and `npm run lint:check` only checks.
- Both lint scripts run eslint with `--cache --cache-strategy content` and share `frontend/.eslintcache`. A run without `--cache` deletes that file, and the pre-commit hook then lints the whole project with type information again, which takes about two minutes instead of a few seconds. The content strategy keeps a branch switch, which only changes file times, from invalidating the cache. The cache does not track types across files, so CI, which starts without one, stays the complete check.
- A `.vue` or `.ts` file under `src/` has at most 600 lines of code, blank lines and comments not counted, and ESLint's `max-lines` fails `lint:check` on a longer one. Locale files, specs and generated files are exempt. A file that grows past the limit is split by responsibility: logic into a `useXxx.ts` composable, a coherent part of the template into a child component, with the props, emits and exposed methods unchanged for its callers.
- The files that were over the limit when it became an error are listed in `frontend/max-lines-baseline.json`, each with the size it had then as its own cap. The baseline only shrinks: a listed file may get shorter but never longer, no file is added to it, and no cap is raised. `npm run lint:check:max-lines` (part of `lint:check`) fails while an entry is no longer needed because its file is gone or fits the limit, and names the listed files that shrank. `npm run lint:check:max-lines -- --write` lowers each cap to its file's current size and drops the entries that are no longer needed. The limit and the counting options live in `frontend/eslint.max-lines.ts`, which the config and the check share.
- Import Vue, vue-router and vue-i18n APIs (`ref`, `computed`, `useRoute`, `useI18n` and the like) explicitly, because nothing imports them for you.
- OpenVue components are the opposite: `unplugin-vue-components` with the OpenVue resolver registers them, so templates use them without an import. Their types and services (`MenuItem`, `useConfirm`) are imported from `openvue/*`.
- Permission checks use `usePermissions().hasPermission(...)`.
- A control the user lacks the permission for stays visible and disabled ([design-look.md](design-look.md)). Its tooltip comes from `useMissingPermission().missing(...)`, which names the first missing permission, and sits on a `span` around the button, since a disabled button shows no tooltip of its own. A control is hidden only for the record's state, such as an action its `actions` do not offer, or for data the user may not read at all.
- A lifecycle action that needs a permission on top of its base one comes back in the response's `blocked_actions` when the state allows it but the reader lacks that permission (orders, order lines and lots, [lifecycle.md section 3](lifecycle.md#3-adding-a-user-action)). Gate the control's visibility on `offersAction(response, action)` and its enabled state on `hasAction` (`core/utils/lifecycleActions.ts`), and take its tooltip from `useMissingPermission().missingForAction(response, action, ...basePermissions)`, which names the first base permission missing and otherwise the blocked one. A context menu entry carries the same text as its `title` and its menu binds `disabledItemTooltipPt` (`shared/utils/menuItemTooltip.ts`).
- A shared component that gates editing on a `canEdit` or `canWrite` prop takes the tooltip as a prop as well (`missingHint` on `FilesSection` and `FileActionButtons`, `takeOverBlocked` on `DocumentLockNotice`). Without it the component keeps hiding the controls, which suits a caller whose flag stands for state.

## 2 styling

- Styling is `<style scoped lang="scss">`. No Tailwind or other utility CSS.
- Never write `@media (prefers-color-scheme: dark)` in a component. The OpenVue theme (`.p-dark`) and its CSS variables handle dark mode.
- The tokens live in `src/assets/styles/main.scss`. A gap, padding or margin is a `--space-1` to `--space-6` token (0.25, 0.5, 0.75, 1, 1.5 and 2rem); padding and margins may also be `0`, `auto`, a `1px` hairline or a negative value that pulls an element over its container's padding, a font size a `--font-size-xs/sm/md/lg/xl` token for text or `--font-size-2xl/3xl/4xl/5xl` for icons and display figures. Sizes relative to the element or the screen (`em`, `vmin`, `clamp()`) stay literal, which is what makes the infoscreen widgets scale.
- The rem root is pinned at 14px on `html`. Following the browser's font-size setting instead is a change to that one rule.
- A colour is an OpenVue variable or an app token. Text on a saturated background (the primary bars, avatars, banners) takes `--on-accent`, on a light accent such as orange `--on-light-accent`, and the header's text and icons take `--header-fg`. Translucent white on such a bar is `--on-accent-muted` for secondary text, `--on-accent-soft` for icons and `--on-accent-hover` for a hover fill. `--paper` stays white in both themes, for QR codes and print and mail previews. Shadows are `--shadow-sm/md/lg`, which deepen in the dark theme, and `--shadow-side` for the overlay sidebar.
- A colour literal (hex, `rgb()`, `rgba()`, `hsl()`, `hsla()`) appears only in a custom property definition, in any property including shorthands such as `border`, `box-shadow` and gradients. A screen with its own fixed palette defines its tokens on its root element, as `AuthLayout.vue` does for the sign-in screens with `--auth-*`.
- A media query takes a breakpoint from `src/assets/styles/_breakpoints.scss` (`$bp-sm` 768px to `$bp-3xl` 2000px, plus two height breakpoints). Vite injects the file into every SCSS block, so a component needs no `@use`.
- A dialog takes the smallest `--dialog-width-sm/md/lg/full` token (`main.scss`) its content fits in, never a literal width. Every dialog is capped at 95vw by `_openvue.scss`, so it needs no `maxWidth` of its own.
- The shared classes in [design-look.md section 9](design-look.md#9-visual-language) are styled once in `main.scss`. A component adds to them in its scoped styles and does not restate them.
- A component never styles OpenVue's internal `.p-*` classes, which are not a public interface and may change with any upgrade. Stylelint rejects them in `.vue` files (`.p-dark`, the theme switch, stays allowed). In order of preference, a component instead puts a named class from `src/assets/styles/_openvue.scss` on the OpenVue component, sets one of the theme's `--p-*` variables on the component or an ancestor (`--p-tabs-tabpanel-padding`, `--p-progressbar-height`, `--p-iconfield-icon-color`), puts a class of its own on the component tag, where it lands on the component's root and carries the scope, or reaches an inner element through pass-through (`:pt="{ text: { class: 'banner-text' } }"`, then `:deep(.banner-text)`). A pattern that repeats goes into `_openvue.scss`, and a true one-off that needs the theme's class names takes a `stylelint-disable` comment with its reason.
- The named classes in `_openvue.scss`: `fill-panel` on a Panel that fills its height (with `--fill-panel-gap` and `--fill-panel-overflow-y`), `fill-tabs` on Tabs that fill theirs (`fill-tabs--contained` when the tab's own content scrolls, `fill-tabs--column` when it is one block), `record-card` with `--scroll` and `--stretch` for the Panels of the detail record grids, `clickable-rows`, `fixed-layout-table` (with `--table-min-width`), `ellipsis-cells` and `nested-table` on a DataTable, `compact-buttons` on a wrapping row of buttons, `sized-drawer` on a Drawer (with `--drawer-width`), `fit-fields` on a narrow form, `select-placeholder-as-value` on a Select whose empty value means all, and `view-menu--wrap`, which `PageLayout` sets for `wrap-menu`. After an OpenVue upgrade this file is the one to check.
- A change to an OpenVue component token that holds everywhere, such as the tab panel padding and background, the toolbar padding or the dialog footer padding, goes into `src/core/config/themePresets.ts`, which lays it over every preset a user can pick.
- Stylelint checks every `<style>` block, the global stylesheets and inline `style` attributes (`npm run lint:check:stylelint`, part of `lint:check`). It enforces the tokens above and catches CSS mistakes such as a duplicate property. A deliberate exception, such as a browser fallback, takes a `stylelint-disable-next-line` comment that says why.
- Text in content is selectable. Controls that are only clicked (buttons, tab strips, table headers, menus, the app's bars) are not. A click on a table row that ends a text selection does not open the row (`installSelectionClickGuard`).
- ESLint checks templates for accessibility (`eslint-plugin-vuejs-accessibility`, all recommended rules on). A deliberate exception takes an `eslint-disable-next-line` comment with its reason.
- A label is tied to its control by a `useId()` prefixed id (`const uid = useId()`, then `:for` on the label and `:id` or `:input-id` on the control), or by `FormField`, which does the same and also hands out `labelId`. `InputText` and `Textarea` take `id`, the other OpenVue inputs take `inputId`. An OpenVue `Select` or `MultiSelect` also needs `aria-labelledby` pointing at the label's id, because its focusable element is a span that a label's `for` cannot name. A control with no visible label, such as a table filter or a cell editor, gets an `aria-label`, usually its column header.
- A caption over a read-only value or a preview is a `<span class="field-caption">`, not a `<label>`, since there is no control to tie it to. It looks like a label in a `.field-row`.
- A settings row with a toggle can be `SettingsToggleRow` (`features/admin-settings/components/`), which ties label and switch together.
- A resizable side panel uses `useResizablePanelWidth` and `PanelResizeHandle`. The handle is a focusable separator: the arrow keys move the edge, with Shift for a larger step, and Home and End jump to the narrowest and widest width.
- Something that only reacts to the mouse gets a keyboard path as well: a hover highlight follows `focusin` and `focusout`, and a clickable `div` gets `role="button"`, `tabindex="0"` and an Enter handler, or is a `Button`.

## 3 promises

- A promise is awaited, returned or handled. `no-floating-promises` and `no-misused-promises` enforce it in script blocks.
- A call that does not reject, such as a sequenced store fetch, `copyToClipboard` or a `router.push` whose navigation failures resolve, is marked `void`.
- Any other background call ends in `.catch(toastOnError())` from `useErrorToast`, which shows the API error as an error toast.
- A menu `command` or a confirmation `accept` is typed to return nothing, so an async one becomes `() => void onAccept()` around a function that handles its own errors.

## 4 API calls

- HTTP goes through the axios instance in `src/core/api/index.ts`, with the base `${VITE_API_URL}/api/v1/web`, the Bearer token, 401 session expiry and 503 `MaintenanceModeError` handling. Never create a second instance.
- API functions live in `features/<x>/api/` and are named `getX`, `createX`, `updateX`, `deleteX` and `<action>X`.
- New calls use `webApi` from `src/core/api/webRequest.ts`, which checks the path, method, path params, query and body against the generated `paths` at compile time and still goes through the shared axios instance.
- `webApi` passes its `config` to axios, so `responseType: 'blob'`, an abort `signal` and progress callbacks work through it, and `postFile` covers single file uploads.
- A call that reads the response headers, such as a download that takes its file name from `Content-Disposition`, stays on the axios instance.
- Routes that exist for several item kinds (demands, allocations, files) come from the factories in `src/shared/api/` (`createDemandApi`, `createFilesApi` and others). Each feature re-exports the functions it uses under its own names in one module.
- Lists use `PageResponse<T> = { items, total, limit, skip }`.
- A list request asks for at most `API_MAX_PAGE_SIZE` (`core/constants/table.ts`), which mirrors the backend's `MAX_PAGE_SIZE`. A larger limit is rejected with a 422.
- A view that needs a whole list rather than one page reads it with `fetchAllPages()` from `core/api/fetchAllPages.ts`, which requests consecutive pages until it holds `total` items. It is for lists that stay small by nature, such as the machine pools or the demands of one project, never for a list that grows with the business.
- A spreadsheet export of a table is the one exception, because the user starts it and it ends in a file. It reads the table's current filter and sort through `useSpreadsheetExport` from `shared/spreadsheet-export`, which pages through the list with `fetchExportRows`, reports its progress, stops on Cancel, asks before more than `EXPORT_CONFIRM_ROWS` rows and refuses more than `EXPORT_MAX_ROWS`. The table and its export build their query params in one composable, as `useBoughtItemsCatalogueQuery` and `useOrdersQuery` do, so the file holds exactly the rows the table filters to.
- A count, a sum or the rows of a growing list that need attention come from a read endpoint that computes them on the server, as the dashboard summary (`GET /dashboard/summary`) counts lots and demands by status and the Todo sources (`GET /todo/sources`) return only the rows that can give a task. Such an endpoint reads the stored fields the list endpoints filter on and never derives a lifecycle status again.
- A picker over a growing list searches on the server as the user types and offers one page of matches: `useRemoteOptions` (`shared/composables/`) for a `Select` of whole rows, as `OrderSelect` and `BoughtItemSelect` do, and `LookupSelect` or `LookupMultiSelect` (`shared/components/forms/`) for ids. The chosen value stays an option when the page does not hold it.

## 5 API types and their lint guards

- Types live in `features/<x>/types/<x>Request.ts` and `<x>Response.ts` and alias `webSchema.ts` through `Schemas['X']` from `core/api/generated`.
- Query parameters are generated too. A list filter type is `QueryOf<'/customers'>`, or `QueryOf<'/x', 'post'>` for another method, from `core/api/webRequest.ts`, keyed by path like a `webApi` call. A sort type is `NonNullable<XFilterParams['order_by']>`.
- Override a field with `Omit` only where the frontend deliberately sends a narrower type, such as a closed union the backend types as a plain string, and say why in one line.
- Response schemas list every field as required ([backend-conventions.md section 4](backend-conventions.md#4-dtos-and-schemas)), so response types alias the schema without narrowing defaulted fields.
- A request field with a plain default comes out required in the generated type although a request may omit it, so request types keep it optional.
- `eslint.config.ts` guards both the wire types and the raw API calls through `no-restricted-syntax`, across `src/**/*.{ts,vue}` except specs, `src/test-utils/` and the generated file.
- The wire type selectors flag an interface, or an alias of an object type, named `*Response` or `*Request`, and any other interface or object type with three or more snake_case members unless its name ends in `Params`, `Query`, `Filter`, `Filters`, `Form` or `State`.
- The object half of `Omit<Schemas['X'], 'a'> & { a: ... }` and an interface that extends another type are not flagged.
- A structural type that several generated responses must satisfy, such as `ControlledDocument`, keeps its own shape with an `eslint-disable-next-line no-restricted-syntax -- <reason>` comment.
- The raw API selectors flag `api.get/post/put/patch/delete` on the axios instance imported from `@/core/api`.
- The files that still call the axios instance directly are listed in `RAW_API_ALLOWLIST`, which only shrinks. Migrate a file to `webApi` and take it off the list, and never add one.

## 6 i18n

- Every user-visible string goes through `t()`.
- Messages live in `src/core/i18n/locales/`, one file per top-level key (a namespace such as `common` or `orders`) and locale: `locales/<namespace>/<namespace>.en-GB.ts` (source and fallback) and `locales/<namespace>/<namespace>.de-AT.ts`, each exporting a default object.
- A namespace that grows large can move a sub-key into its own file next to it, as `tools/driveSizing.en-GB.ts` does.
- The main files `en-GB.ts` and `de-AT.ts` hold no messages themselves. They import every namespace file of their locale and assign each one to its key, in the same order in both files.
- To add a namespace, create both locale files under `locales/<namespace>/`, then add the import and the `<namespace>:` assignment to `en-GB.ts` and to `de-AT.ts`.
- New keys inside an existing namespace go into its two locale files only.
- `npm run check:i18n` fails on a key missing in either locale, English or German, on a namespace file without its sibling in the other locale, and on main files whose namespace lists differ. A new key therefore always lands in both locale files at once.

## 7 German copy and language

- German copy, in the UI and in mail templates, addresses the user informally, never with the formal address.
- The formal pronouns are listed under `localeRules.formalAddressWords` in `locales/localeRules/localeRules.de-AT.ts`, and `npm run check:i18n` fails when a German string uses one.
- German appears only in locale files, mail templates and handbook pages. Code, identifiers, comments, log messages, tests, test data and docs are English.
- A test of German behaviour derives its expected text from the de-AT locale file or from `Intl` with the de-AT locale.
- Words Glados has to recognise in German input are data, not code. The spreadsheet imports' column names are an admin setting (Settings, Data import), which starts empty and is filled by importing the files of the root `templates/data-import/` folder, one per language.
- Text the backend writes in the recipient's language outside a mail template, such as the title and sentence of a bundled meeting notification, is data as well. It lives in the module's locale data files, such as `backend/src/modules/workspace/adapters/outbound/locale/meeting_activity.<language>.json`, which an adapter reads and the composition root hands to the use case, while the domain only puts the phrases together.
- The casing of English labels, headers and messages is in [design-look.md section 10](design-look.md#10-copy).

## 8 state and live updates

- Live updates come from `core/realtime/`.
- A paginated table patches its rows with `useLiveRows`.
- Any other view refetches with `useLiveRefresh(resources, refetch, { debounceMs, filter })`, which debounces the signals, refetches once after the stream reconnects and drops a refetch that fails.
- Neither live helper needs a polling timer beside it.
- `localStorage` goes through `safeStorage` (`core/utils/safeStorage.ts`), whose reads return null and writes return false when storage is blocked, full or missing, instead of throwing.
- The import drafts write through `core/stores/draftWrites.ts`, which debounces the write of a whole sheet.
- List stores use `useSequencedFetch` with a `bumpFetchEpoch` guard, so a stale response never overwrites a newer one.
- `storeResetPlugin` (`src/core/stores/resetOnLogout.ts`) resets every store on logout except the ids in `DEFAULT_EXCLUDED_STORE_IDS`. A new singleton store must be added there.

## 9 shared components and OpenVue pitfalls

- The demand tables of the item kinds share their frame through `shared/components/demands/DemandsTableShell.vue` and the composables `useDemandTableData` and `useDemandGrouping`.
- The shell holds paging, the filter bar, the grouping header, selection, the actions and row number columns, the desired delivery, creator and created columns, the context menu and bulk cancel.
- Kind-specific columns, row buttons, menu entries and dialogs stay in the feature's `*DemandsTable.vue` and go in through the shell's slots and props.
- A `DataTable` with `selectionMode="single"` loses keyboard row access if it also binds `v-model:selection`.
- A table whose rows are bulk edited keeps its checkbox column and select all box in view for every user with the write right, not only while the edit panel is open: the demand tables through `DemandsTableShell`, the catalogue tables through `useCatalogueRowSelection`, the lots table through `useLotsTableBulkSelection`. A plain click or Enter still opens the row and leaves the checked rows alone, ctrl-click and shift-click pick rows, and a user without the right keeps single selection with full keyboard access.
- A `DataTable` with `filterDisplay="row"` crashes without a `filters` binding, so pass a decoy object (see `BoughtItemsDemandsTable` and `MadeItemsDemandsTable`).
- A table's Export button is `SpreadsheetExportButton` in its controls bar, after Edit on a catalogue (the `after-edit` slot of `CatalogueControlsBar`) and after the import button on a demand list. A table without row selection, such as the orders, passes no `selectedCount` and gets a plain button. A catalogue's columns come from `tableExportColumns`: the visible columns in their order, a cell per field whose table cell renders more than its raw value, the person after each date column and the record's lasting `/resolve` link last. A demand list has fixed columns from `demandExportColumns` (`shared/components/demands/`) with the kind's item columns in the middle and the demanded item's link last, since a demand has no page. A record that becomes several sheet rows, such as an order with its lines, is expanded by the source's `toSheetRows`. A value stays its type, so a number, a date or a price in cents is written as one and a code stays text, and a picture or file column is left out.
- `TabPanel` renders a fragment, so a class on it gets no scope attribute and a scoped rule for that class never matches. Style it from `TabPanels` through `:deep()`, as `LotDetailRecordGrid` does.
