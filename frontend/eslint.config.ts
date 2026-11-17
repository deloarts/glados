import { existsSync, readdirSync } from 'node:fs'
import type { Linter } from 'eslint'
import { globalIgnores } from 'eslint/config'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import pluginVue from 'eslint-plugin-vue'
import pluginVueA11y from 'eslint-plugin-vuejs-accessibility'
import pluginVitest from '@vitest/eslint-plugin'
import pluginOxlint from 'eslint-plugin-oxlint'
import skipFormatting from 'eslint-config-prettier/flat'

import {
  MAX_LINES_FILES,
  MAX_LINES_IGNORES,
  MAX_LINES_OPTIONS,
  readMaxLinesBaseline,
} from './eslint.max-lines'

// The max-lines rule at the shared counting options with the given cap.
const maxLinesRule = (max: number): Linter.RuleEntry => ['error', { ...MAX_LINES_OPTIONS, max }]

// To allow more languages other than `ts` in `.vue` files, uncomment the following lines:
// import { configureVueProject } from '@vue/eslint-config-typescript'
// configureVueProject({ scriptLangs: ['ts', 'tsx'] })
// More info at https://github.com/vuejs/eslint-config-typescript/#advanced-setup

// Cross-feature import walls. These are the features that carry a
// public barrel (`src/features/<feature>/index.ts`) other features must
// import through instead of reaching into their internals. The list is read
// from the folders, so adding a barrel puts a feature behind the wall, and
// features nobody imports from need no barrel just to satisfy the rule.
// Production and production-machines are two separate barreled features,
// walled off from each other on purpose, even though they are closely related.
const FEATURES_DIR = new URL('./src/features/', import.meta.url)
const BARRELED_FEATURES = readdirSync(FEATURES_DIR, { withFileTypes: true })
  .filter((entry) => entry.isDirectory() && existsSync(new URL(`${entry.name}/index.ts`, FEATURES_DIR)))
  .map((entry) => entry.name)
  .sort()

const restrictedImportPattern = (feature: string) => ({
  group: [`@/features/${feature}/**`],
  message: `Import '${feature}' through its public barrel '@/features/${feature}' instead of a deep import into its internals.`,
})

// Explicit `Linter.RuleEntry` return type gives the ['error', options] tuple
// literal a contextual type, so `'error'` narrows to the literal instead of
// widening to `string` (which is what happens when this is built inline
// inside a plain `.map()` with no surrounding type to check against).
// PDF reports are built from the blocks of `@/shared/reports` only, so every
// report shares one look and the PDF library stays replaceable. This rides
// along with the feature walls because flat config would otherwise replace
// one `no-restricted-imports` option object with the other.
const noPdfLibraryImports = {
  group: ['pdfmake', 'pdfmake/**'],
  message: 'Build reports from the blocks of @/shared/reports, which also re-exports the pdfmake types a builder needs.',
}

const noDeepFeatureImports = (
  patterns: { group: string[]; message: string }[],
): Linter.RuleEntry => ['error', { patterns: [...patterns, noPdfLibraryImports] }]

// Every feature file is banned from deep-importing any *other* barreled
// feature's internals (`@/features/<feature>/**`) and must go through the
// bare barrel specifier (`@/features/<feature>`) instead. Each config object
// below covers a disjoint set of files (one per barreled feature, plus a
// catch-all for every non-barreled feature), because a plain `no-restricted-
// imports` entry per feature would clobber the others for any file matching
// more than one - flat config replaces a rule's whole option object per
// file rather than merging `patterns` arrays across config objects.
const featureImportBoundaries = [
  ...BARRELED_FEATURES.map((feature) => ({
    name: `app/feature-boundary-${feature}`,
    files: [`src/features/${feature}/**/*.{ts,tsx,vue}`],
    rules: {
      'no-restricted-imports': noDeepFeatureImports(
        BARRELED_FEATURES.filter((f) => f !== feature).map(restrictedImportPattern),
      ),
    },
  })),
  {
    name: 'app/feature-boundary-other',
    files: ['src/features/**/*.{ts,tsx,vue}'],
    ignores: BARRELED_FEATURES.map((feature) => `src/features/${feature}/**`),
    rules: {
      'no-restricted-imports': noDeepFeatureImports(BARRELED_FEATURES.map(restrictedImportPattern)),
    },
  },
  // The router and the app shell sit above every feature and take them
  // through their barrels too; a lazy `import()` of a view stays unchecked.
  {
    name: 'app/feature-boundary-shell',
    files: ['src/router/**/*.{ts,tsx,vue}', 'src/app/**/*.{ts,tsx,vue}', 'src/App.vue'],
    rules: {
      'no-restricted-imports': noDeepFeatureImports(BARRELED_FEATURES.map(restrictedImportPattern)),
    },
  },
]

// A report builder chooses its look by name, from the styles and spacing
// presets of `@/shared/reports`, and never writes sizes, colours, fonts or
// margins itself, so a design change is made once in the engine and every
// report stays alike. Casting to `Content` would hide a hand-made pdfmake node.
const REPORT_STYLE_PROPERTIES = ['fontSize', 'color', 'fillColor', 'margin', 'bold', 'italics', 'font', 'lineHeight', 'decoration']
const REPORT_STYLE_MESSAGE =
  'Report builders style text by name. Use a block from @/shared/reports with a named style or spacing preset, or add one to shared/reports/utils/styles.ts.'
const noRawReportStyling = [
  { selector: `Property[key.name=/^(${REPORT_STYLE_PROPERTIES.join('|')})$/]`, message: REPORT_STYLE_MESSAGE },
  { selector: 'Literal[value=/^#[0-9a-fA-F]{3,8}$/]', message: REPORT_STYLE_MESSAGE },
  { selector: "TSAsExpression > TSTypeReference.typeAnnotation[typeName.name='Content']", message: REPORT_STYLE_MESSAGE },
]

// Frontend request/response types must be sourced from the generated
// OpenAPI schema (`export type XResponse = Schemas['XResponse']`, see
// core/types/userResponse.ts, and `QueryOf<'/path'>` from
// core/api/webRequest.ts for list filters), not hand-rolled. A hand-written
// shape silently drifts from the backend instead of failing the
// `check:api-types` gate. The first two selectors catch a plain interface or
// a type alias whose value is a raw object literal named *Response/*Request;
// an alias built from `Schemas[...]` (an indexed access, or an
// intersection/Omit wrapping one) is unaffected. The last two catch any
// other interface or object type with three or more snake_case members,
// which in this codebase is often a copy of a backend shape. Query
// param, filter and form state types are exempt by name, because they are
// frontend-built shapes that only reuse the backend's field names.
const WIRE_TYPE_MESSAGE =
  "Hand-written interfaces named *Response/*Request drift from the backend silently instead of failing the check:api-types gate. Alias the generated schema instead, e.g. export type XResponse = Schemas['XResponse'] (see core/types/userResponse.ts for the pattern, including how to override one field). If this type genuinely has no backend schema, rename it to drop the Response/Request suffix, or add its file to WIRE_TYPE_ALLOWLIST here with a comment explaining why."
const SNAKE_CASE_MESSAGE =
  "This type has three or more snake_case members, so it looks like a hand-written copy of a backend shape that will drift silently. Alias the generated schema (Schemas['X'], or QueryOf<'/path'> for query params), narrowing single fields with Omit where needed. If it is a frontend-built query, filter or form shape, name it *Params, *Query, *Filter, *Form or *State; otherwise disable this line with a reason."
const SNAKE_CASE_KEY = String.raw`/^[a-z][a-z0-9]*(_[a-z0-9]+)+$/`
const SNAKE_CASE_MEMBER = `TSPropertySignature[key.name=${SNAKE_CASE_KEY}]`
const HAS_THREE_SNAKE_CASE_MEMBERS = `:has(> ${SNAKE_CASE_MEMBER} ~ ${SNAKE_CASE_MEMBER} ~ ${SNAKE_CASE_MEMBER})`
const SNAKE_CASE_EXEMPT_NAME = '/(Params|Query|Filters?|Form|State)$/'
const WIRE_NAME = '/(Response|Request)$/'
// The object half of `Omit<Schemas['X'], 'a'> & { a: Narrowed }`, which
// overrides fields of an aliased schema rather than restating it. An
// interface that extends another type is the same pattern and is exempt too.
const SCHEMA_OVERRIDE_LITERAL = 'TSIntersectionType:has(> TSTypeReference, > TSIndexedAccessType) > TSTypeLiteral'
const noHandWrittenWireTypes = [
  { selector: `TSInterfaceDeclaration[id.name=${WIRE_NAME}]`, message: WIRE_TYPE_MESSAGE },
  { selector: `TSTypeAliasDeclaration[id.name=${WIRE_NAME}] > TSTypeLiteral`, message: WIRE_TYPE_MESSAGE },
  {
    selector: `TSInterfaceDeclaration:not([id.name=${WIRE_NAME}]):not([id.name=${SNAKE_CASE_EXEMPT_NAME}]):not(:has(> TSInterfaceHeritage)) > TSInterfaceBody${HAS_THREE_SNAKE_CASE_MEMBERS}`,
    message: SNAKE_CASE_MESSAGE,
  },
  {
    selector: `TSTypeLiteral${HAS_THREE_SNAKE_CASE_MEMBERS}:not(TSTypeAliasDeclaration[id.name=${WIRE_NAME}] > TSTypeLiteral):not(TSTypeAliasDeclaration[id.name=${SNAKE_CASE_EXEMPT_NAME}] TSTypeLiteral):not(TSInterfaceDeclaration[id.name=${SNAKE_CASE_EXEMPT_NAME}] TSTypeLiteral):not(${SCHEMA_OVERRIDE_LITERAL})`,
    message: SNAKE_CASE_MESSAGE,
  },
]

// Files that may keep hand-written wire-shaped types.
const WIRE_TYPE_ALLOWLIST = [
  // Describes the generic OpenAPI 3.1 document shape the API docs panel
  // renders (a spec format, not a single backend response model), so
  // there is nothing in Schemas[...] to alias.
  'src/features/admin-settings/types/openApiTypes.ts',
]

// HTTP calls go through `webApi` (core/api/webRequest.ts), which checks the
// path, method, params, query and body against the generated schema. A raw
// `api.get<T>()` on the axios instance from '@/core/api' only asserts T, so a
// renamed route or a changed response still passes type-check. The rule
// flags the verb methods of the default import named `api`, and a default
// import of the instance under another name, which would dodge the check.
const RAW_API_MESSAGE =
  "Call the backend through webApi from '@/core/api/webRequest' (or postFile for an upload), which checks the route, query, body and response against the generated schema. The raw axios instance only asserts the response type."
const noRawApiCalls = [
  {
    selector: `Program:has(ImportDeclaration[source.value='@/core/api'] > ImportDefaultSpecifier[local.name='api']) MemberExpression[object.name='api'][property.name=/^(get|post|put|patch|delete)$/]`,
    message: RAW_API_MESSAGE,
  },
  {
    selector: `ImportDeclaration[source.value='@/core/api'] > ImportDefaultSpecifier[local.name!='api']`,
    message: RAW_API_MESSAGE,
  },
]

// Files that still call the raw axios instance. The list only shrinks, and a
// new file must never be added to it; a new call that webApi cannot express
// yet is a reason to extend webApi instead.
const RAW_API_ALLOWLIST = [
  // These read response headers (the file name and the preview warnings),
  // which webApi does not return, so they stay on the axios instance.
  'src/features/print-labels/api/downloadPrintTemplate.ts',
  'src/features/print-labels/api/previewPrintTemplate.ts',
]

// The rules above and the report styling rule all use `no-restricted-syntax`.
// Flat config replaces a rule's whole option list per file rather than
// merging it, so every file gets one entry assembled from the selector sets
// that apply to it: the base config covers all application source, the
// report builders add their styling set, and each allowlisted file gets an
// entry without the set it is exempt from.
const APP_SOURCE = ['src/**/*.{ts,vue}']
const APP_SOURCE_IGNORES = [
  'src/**/__tests__/**',
  'src/**/*.spec.ts',
  'src/test-utils/**',
  'src/core/api/generated/**',
]
const REPORT_BUILDERS = 'src/features/**/*{report,Report}*.ts'
const isReportBuilder = (file: string) => /^src\/features\/(.+\/)?[^/]*(report|Report)[^/]*\.ts$/.test(file)

const restrictedSyntax = (sets: { wire: boolean; raw: boolean; report: boolean }): Linter.RuleEntry => {
  const selectors = [
    ...(sets.wire ? noHandWrittenWireTypes : []),
    ...(sets.raw ? noRawApiCalls : []),
    ...(sets.report ? noRawReportStyling : []),
  ]
  return selectors.length > 0 ? ['error', ...selectors] : 'off'
}

const allowlistedFiles = [...new Set([...WIRE_TYPE_ALLOWLIST, ...RAW_API_ALLOWLIST])]
const restrictedSyntaxConfigs = [
  {
    name: 'app/restricted-syntax',
    files: APP_SOURCE,
    ignores: APP_SOURCE_IGNORES,
    rules: { 'no-restricted-syntax': restrictedSyntax({ wire: true, raw: true, report: false }) },
  },
  {
    name: 'app/report-builders-style-by-name',
    files: [REPORT_BUILDERS],
    ignores: APP_SOURCE_IGNORES,
    rules: { 'no-restricted-syntax': restrictedSyntax({ wire: true, raw: true, report: true }) },
  },
  ...allowlistedFiles.map((file) => ({
    name: `app/restricted-syntax-allowlist:${file}`,
    files: [file],
    rules: {
      'no-restricted-syntax': restrictedSyntax({
        wire: !WIRE_TYPE_ALLOWLIST.includes(file),
        raw: !RAW_API_ALLOWLIST.includes(file),
        report: isReportBuilder(file),
      }),
    },
  })),
]

// Specs select elements by role, label, text or data-testid, never by
// OpenVue's internal `.p-*` classes or `.mdi-*` icon classes: an OpenVue
// upgrade or an icon rename would otherwise break specs whose behaviour did
// not change. A spec that genuinely asserts on one of those classes (for
// example which icon a button shows) opts out with
// `// eslint-disable-next-line no-restricted-syntax -- <reason>`.
const OPENVUE_INTERNAL_SELECTOR = String.raw`/(^|[\s>+~,(])\.(p|mdi)-/`
const OPENVUE_INTERNAL_SELECTOR_MESSAGE =
  'Do not select on OpenVue internal .p-* or .mdi-* icon classes in specs. Add a data-testid to the component (through its pt pass-through options when OpenVue renders the element) or select by role, label or text. If the class itself is what the test asserts, disable this line with a reason.'
const noOpenVueInternalSelectors: Linter.RuleEntry = [
  'error',
  {
    selector: `Literal[value=${OPENVUE_INTERNAL_SELECTOR}]`,
    message: OPENVUE_INTERNAL_SELECTOR_MESSAGE,
  },
  {
    selector: `TemplateElement[value.raw=${OPENVUE_INTERNAL_SELECTOR}]`,
    message: OPENVUE_INTERNAL_SELECTOR_MESSAGE,
  },
]

export default defineConfigWithVueTs(
  {
    name: 'app/files-to-lint',
    files: ['**/*.{vue,ts,mts,tsx}'],
  },

  globalIgnores(['**/dist/**', '**/dist-ssr/**', '**/coverage/**', 'src/core/api/generated/**']),

  ...pluginVue.configs['flat/strongly-recommended'],
  vueTsConfigs.recommended,

  // Accessibility checks on templates. A label counts as tied to its control
  // when it wraps it or names its id. Moving focus to a dialog's first field
  // is the dialog pattern, so autofocus is allowed. An OpenVue Select takes
  // its name from aria-labelledby, since its focusable element is a span that
  // a label's for cannot name. A deliberate exception takes a disable comment
  // with its reason.
  ...pluginVueA11y.configs['flat/recommended'],
  {
    name: 'app/accessibility',
    rules: {
      // OpenVue's Tag renders its value as text, which names a link around it.
      'vuejs-accessibility/anchor-has-content': ['error', { accessibleChildren: ['Tag'] }],
      // OpenVue controls whose root holds a native input are labelled by a
      // wrapping label just like the input itself. Select is not among them,
      // its focusable element is a span that a label cannot name.
      'vuejs-accessibility/label-has-for': [
        'error',
        {
          required: { some: ['nesting', 'id'] },
          controlComponents: ['Checkbox', 'ToggleSwitch', 'RadioButton', 'InputText', 'InputNumber', 'Textarea', 'DatePicker', 'Password'],
        },
      ],
      'vuejs-accessibility/no-autofocus': 'off',
    },
  },

  // TypeScript optional props (`prop?: T`) are intentionally `undefined` when
  // the caller omits them, and a real default is already expressed through
  // `withDefaults` where one exists, so this rule's "give every prop a
  // default" stance does not fit how props are declared in this codebase.
  {
    name: 'app/no-require-default-prop',
    rules: {
      'vue/require-default-prop': 'off',
    },
  },

  {
    ...pluginVitest.configs.recommended,
    files: ['src/**/__tests__/*'],
    rules: {
      ...pluginVitest.configs.recommended.rules,
      // Specs build tiny inline `defineComponent()` fixtures to mount as test
      // doubles, often several per file for different scenarios. That is not
      // the "multiple real SFCs sharing a file" case this rule guards against
      // in application code.
      'vue/one-component-per-file': 'off',
    },
  },

  // A promise nobody awaits or catches turns a failed request into an
  // unhandled rejection the user never sees. These two rules need type
  // information, so defineConfigWithVueTs turns on the TypeScript project
  // service for every .ts and .vue file once a config enables them. They see
  // script blocks only. A template handler that returns a promise is not
  // checked, and Vue hands its rejection to the global error handler, which
  // shows the generic error toast. defineConfigWithVueTs keeps the `files` of
  // a config with type-aware rules but drops its `ignores`, which is why the
  // specs opt out in the untyped parse config below.
  {
    name: 'app/promise-handling',
    files: APP_SOURCE,
    rules: {
      '@typescript-eslint/no-floating-promises': 'error',
      '@typescript-eslint/no-misused-promises': 'error',
    },
  },

  ...restrictedSyntaxConfigs,

  {
    name: 'app/no-openvue-internal-selectors-in-specs',
    files: ['src/**/__tests__/**/*.spec.ts'],
    rules: {
      'no-restricted-syntax': noOpenVueInternalSelectors,
    },
  },

  ...featureImportBoundaries,

  // Specs and the Node scripts run no type-aware rule and skip the project
  // service, which saves about a third of the time typed linting adds. The
  // scripts belong to no tsconfig and could not be type-checked anyway.
  {
    name: 'app/untyped-parse',
    files: ['src/**/__tests__/**', 'src/**/*.spec.ts', 'scripts/**'],
    languageOptions: { parserOptions: { projectService: false } },
    rules: {
      '@typescript-eslint/no-floating-promises': 'off',
      '@typescript-eslint/no-misused-promises': 'off',
    },
  },

  ...pluginOxlint.buildFromOxlintConfigFile('.oxlintrc.json'),

  // A file over the limit fails lint. The files that were over it when the
  // limit became an error each get their own cap from max-lines-baseline.json,
  // the size they had then, so they can shrink but not grow. Generated files
  // are ignored globally above.
  {
    name: 'app/max-lines',
    files: MAX_LINES_FILES,
    ignores: MAX_LINES_IGNORES,
    rules: {
      'max-lines': maxLinesRule(MAX_LINES_OPTIONS.max),
    },
  },
  ...Object.entries(readMaxLinesBaseline()).map(([file, max]) => ({
    name: `app/max-lines-baseline/${file}`,
    files: [file],
    rules: {
      'max-lines': maxLinesRule(max),
    },
  })),

  skipFormatting,
)
