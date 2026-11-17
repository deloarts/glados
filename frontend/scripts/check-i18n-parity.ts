/**
 * i18n key-parity gate.
 *
 * en-GB is the app's `fallbackLocale` (see src/core/i18n/index.ts), so a key
 * missing there has nothing to fall back to and renders as a raw key path
 * in the UI. A key missing in de-AT falls back to English silently, so a
 * German user meets an English string in the middle of German copy. Both
 * fail the build: every key exists in both locales.
 *
 * Both locales are also checked for the same namespace layout: every
 * `<namespace>.en-GB.ts` file needs a `<namespace>.de-AT.ts` sibling and the
 * other way round, and both main files must assign the same top-level
 * namespaces in the same order, each from its own namespace file.
 *
 * Run: npm run check:i18n
 */
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

import { Permission } from '../src/core/auth/permissions'
import { AUTH_PROVIDERS } from '../src/core/auth/authProviders'
import { DEMAND_STATUSES } from '../src/core/utils/demandStatus'
import { PROJECT_STATUSES } from '../src/features/projects/utils/projectStatus'
import { TODO_CATEGORIES } from '../src/features/todo/types/todoTask'
import { GANTT_RESOLUTIONS } from '../src/features/production/planning/utils/productionPlanningScales'
import {
  MANUFACTURING_COMPLEXITIES,
  productionOrderStatusSeverity,
  productionOrderPrioritySeverity,
} from '../src/features/production/utils/productionOrderStatus'
import {
  LOT_STATUSES,
  LOT_PRIORITIES,
  lotPositionKindSeverity,
  lotPositionStatusSeverity,
  lotPositionStatusKey,
} from '../src/features/production/utils/lotStatus'
import { catalogueStatusSeverity } from '../src/shared/utils/catalogueStatus'
import {
  PDM_DOCUMENT_CATEGORIES,
  PDM_RECONCILIATION_CATEGORIES,
} from '../src/features/admin-settings/types/adminSettingsTypes'
import {
  TIME_TRACKING_DAY_STATUSES,
  TIME_TRACKING_INVALID_REASONS,
} from '../src/features/time-tracking/types/timeTrackingTypes'

import type { ProductionOrderStatus, ProductionOrderPriority } from '../src/features/production/types/productionOrdersResponse'
import type { LotPositionKind, LotPositionStatus } from '../src/features/production/types/productionLotsResponse'

type Messages = Record<string, unknown>

// ── Namespace files ─────────────────────────────────────────────────────
//
// Each top-level key of a locale lives in its own file under
// locales/<namespace>/, which the main en-GB.ts or de-AT.ts imports and
// assigns. A namespace file that exists for one locale only, or a main file
// that assigns a different namespace list than the other, means one locale
// silently lost or gained a whole namespace, so both fail the build.

const LOCALES_DIR = fileURLToPath(new URL('../src/core/i18n/locales/', import.meta.url))
const LOCALE_FILE_NAMES = ['en-GB', 'de-AT'] as const

function namespaceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) return entry.name === '__tests__' ? [] : namespaceFiles(path)
    return dir !== LOCALES_DIR && /\.(en-GB|de-AT)\.ts$/.test(entry.name)
      ? [relative(LOCALES_DIR, path)]
      : []
  })
}

const namespaceFileSet = new Set(namespaceFiles(LOCALES_DIR))
const namespaceFileGaps = [...namespaceFileSet].flatMap((file) => {
  const [own, other] = file.endsWith('.en-GB.ts') ? ['en-GB', 'de-AT'] : ['de-AT', 'en-GB']
  const sibling = file.replace(new RegExp(`\\.${own}\\.ts$`), `.${other}.ts`)
  return namespaceFileSet.has(sibling) ? [] : [`${file} has no ${sibling} sibling`]
})

// Reads `  <namespace>: <importName>,` assignments and the matching
// `import <importName> from './<namespace>/<namespace>.<locale>'` lines of a
// main file, so a namespace written inline instead of in its own file shows
// up as a gap too.
function mainFileNamespaces(locale: string): { namespaces: string[]; gaps: string[] } {
  const source = readFileSync(join(LOCALES_DIR, `${locale}.ts`), 'utf8')
  const imports = new Map(
    [...source.matchAll(/^import (\w+) from '\.\/([^']+)'$/gm)].map((m) => [m[1], m[2]]),
  )
  const body = source.slice(source.indexOf('export default {'))
  const namespaces: string[] = []
  const gaps: string[] = []
  for (const line of body.split('\n').slice(1)) {
    if (line === '}' || line === '') continue
    const match = /^ {2}(\w+): (\w+),$/.exec(line)
    if (!match) {
      gaps.push(`${locale}.ts: "${line.trim()}" is not a namespace assignment`)
      continue
    }
    const [, namespace, importName] = match as unknown as [string, string, string]
    namespaces.push(namespace)
    const expected = `${namespace}/${namespace}.${locale}`
    if (imports.get(importName) !== expected) {
      gaps.push(`${locale}.ts: ${namespace} is not imported from ./${expected}`)
    } else if (!existsSync(join(LOCALES_DIR, `${expected}.ts`))) {
      gaps.push(`${locale}.ts: ${namespace} imports ./${expected}, which does not exist`)
    }
  }
  return { namespaces, gaps }
}

const [enMain, deMain] = LOCALE_FILE_NAMES.map(mainFileNamespaces) as [
  ReturnType<typeof mainFileNamespaces>,
  ReturnType<typeof mainFileNamespaces>,
]
const namespaceListGaps: string[] = [...enMain.gaps, ...deMain.gaps]
if (enMain.namespaces.join(',') !== deMain.namespaces.join(',')) {
  const enOnly = enMain.namespaces.filter((ns) => !deMain.namespaces.includes(ns))
  const deOnly = deMain.namespaces.filter((ns) => !enMain.namespaces.includes(ns))
  namespaceListGaps.push(
    enOnly.length || deOnly.length
      ? `namespace lists differ, only in en-GB.ts: [${enOnly.join(', ')}], ` +
          `only in de-AT.ts: [${deOnly.join(', ')}]`
      : 'en-GB.ts and de-AT.ts assign the same namespaces in a different order',
  )
}

const namespaceGaps = [...namespaceFileGaps, ...namespaceListGaps]
if (namespaceGaps.length > 0) {
  console.error(`\n✖ ${namespaceGaps.length} namespace file mismatch(es) between the locales:`)
  namespaceGaps.forEach((gap) => console.error(`  ${gap}`))
  console.error('')
  process.exit(1)
}

// The locales load only after the namespace check, so a missing namespace
// file is reported by name instead of as a module resolution error.
const { default: enGB } = await import('../src/core/i18n/locales/en-GB')
const { default: deAT } = await import('../src/core/i18n/locales/de-AT')

function flatten(obj: Messages, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key
    return value && typeof value === 'object' && !Array.isArray(value)
      ? flatten(value as Messages, path)
      : [path]
  })
}

type LeafEntry = { key: string; value: string }

function flattenLeaves(obj: Messages, prefix = ''): LeafEntry[] {
  return Object.entries(obj).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return flattenLeaves(value as Messages, path)
    }
    return typeof value === 'string' ? [{ key: path, value }] : []
  })
}

const enKeys = new Set(flatten(enGB as Messages))
const deKeys = new Set(flatten(deAT as Messages))

const missingInEn = [...deKeys].filter((key) => !enKeys.has(key)).sort()
const missingInDe = [...enKeys].filter((key) => !deKeys.has(key)).sort()

if (missingInDe.length > 0) {
  console.error(
    `\n✖ ${missingInDe.length} key(s) missing in de-AT (these fall back to English for every ` +
      `German-speaking user):`,
  )
  missingInDe.forEach((key) => console.error(`  ${key}`))
}

if (missingInEn.length > 0) {
  console.error(
    `\n✖ ${missingInEn.length} key(s) missing in en-GB (the fallback locale, these render ` +
      `as raw key paths to every English-speaking user):`,
  )
  missingInEn.forEach((key) => console.error(`  ${key}`))
}

if (missingInDe.length > 0 || missingInEn.length > 0) {
  console.error('')
  process.exit(1)
}

// ── Dynamically-built i18n keys ─────────────────────────────────────────
//
// `grep -rnE "t\(\`|t\('[a-zA-Z.]+' \+ " src --include=*.vue --include=*.ts`
// finds every call site that builds a t() key at runtime (a template string
// or a string concatenation) rather than passing a literal, around 300 call
// sites as of this writing. flatten() above only ever sees the two locale
// files, so none of those call sites are checked by the plain key diff
// above, a status enum can grow a new member and the missing translation
// would only surface when someone actually picks that value in the UI.
//
// Each call site was grouped by its key prefix (its "family") and traced
// back to whatever TypeScript value supplies the interpolated part. Where
// that value is a value-level constant or a Record whose keys are the
// interesting union (something this script can actually import and
// enumerate), the family is wired below: every member's key is asserted to
// exist in en-GB and in de-AT, and a gap in either fails the build, the same
// as a plain missing key.
//
// A large remainder cannot be checked this way, for one of four reasons,
// and is intentionally left unverified rather than faked with a duplicated
// literal list that would silently drift from the real source:
//
// (a) RUNTIME OR CONFIGURATION DATA. The interpolated value is not a fixed
//     frontend enum at all, it is live API/store data, or a per-usage
//     configuration string handed to a generic component.
//       - `${props.i18nPrefix}.*` / `${adapter.i18nPrefix}.*` family: the
//         prefix is a plain string prop, a different literal per caller, on
//         TokenManagementTable, TokenFormDialog, TokenUsageLogDialog,
//         TokenManagementControls, SimpleNamedEntityFormDialog,
//         SimpleNamedEntityManagementTable, DemandFulfillFromStockDialog,
//         DemandImportDialog, DemandImportReviewTable,
//         DemandImportRowFormDialog, ItemDemandsControlsBar,
//         CatalogueControlsBar, useManagementResourceActions,
//         ItemMergeDialog.
//       - `printLabels.classifiers/triggers/copiesRules.*` and the matching
//         `printDockets.*` keys: PrintTemplateResponse types classifier,
//         trigger and copies_rule as plain strings, there is no frontend
//         union to enumerate.
//       - `main.footer.${link.key}`: publicBrandingStore.footerLinks
//         (host-configured branding links).
//       - `main.sidebar.${page}.label`: hostStore.startPages
//         (host-configured).
//       - `productionSchedule.autoPlan.progress.${stage}`: the live
//         run/observer SSE stage string.
//       - `production.lots.contextMenu.${i18nStem}Sent/Failed` and
//         `productionQueue.card.${i18nStem}Sent/Failed`: the print-job kind
//         is derived per call at runtime.
//       - `common.live.${liveStore.status}`: live websocket connection
//         state.
//       - `production.lots.detail.record.execution.${cmp.metric}`: a
//         per-row comparison metric name off computed execution data.
//       - `search.row.via.${hit.via_kind}`: a field off the search API
//         response.
//       - `adminSettings.itemFields.fields/.notes.*`: keyed by the item
//         field names the backend's ownership table response lists, not a
//         fixed frontend union.
//
// (b) CLOSED TYPE UNION, NO RUNTIME VALUE. A `type X = 'a' | 'b'` (often
//     generated from the OpenAPI schema in core/api/generated/webSchema.ts)
//     with nothing exported at the value level to iterate, types are erased
//     at runtime so there is nothing for this script to import.
//       - `orders.status.*` (OrderStatus), `orders.items.status.*`
//         (OrderItemStatus).
//       - `production.machineDetail.state.*` (a state derived in a
//         composable).
//       - `printers.kinds.*` (PrinterKind), `printers.history.statuses.*` /
//         `.triggers.*` (PrintJobResponse status/trigger).
//       - `adminSettings.backups.status.*` / `.trigger.*` (BackupRunStatus /
//         BackupTrigger).
//       - `adminSettings.notifications.severities.*` (AnnouncementSeverity).
//       - `adminSettings.numbering.patternResult.*` (PatternTestResult).
//       - `adminSettings.pdmSyncLog.runs.trigger.*` / `.entries.action.*`
//         (PdmSyncTrigger / PdmSyncEntryAction).
//       - `adminSettings.solidworksPdm.pdm.sync.status.states.*`,
//         `boughtItems.catalogue.pdmSyncStates.*`,
//         `madeItems.catalogue.pdmSyncStates.*`,
//         `pdmPreview.panel.syncStates.*` (all the same PdmSyncState).
//       - `orders.files.categories.*` / `.categoryShort.*`
//         (OrderFileCategory).
//       - `productionWip.status.*` / `.priority.*` (WipLotResponse status
//         and priority).
//       - `production.lots.detail.record.lot.origin.*` / `.followUp.*` and
//         `production.lots.columns.lineageIconTooltip.*` (LotOriginDisposition).
//       - `production.lots.detail.record.sourceDemand.allocationSource.*`
//         (the allocation's source field).
//       - `madeItems.create.revision.predecessorStatus.sideEffects.*`
//         (RevisionPredecessorStatus).
//       - `adminSettings.itemFields.owners.*` (ItemFieldOwner).
//
// (c) LOCAL CONSTANT, NOT EXPORTED. The backing list is a genuine fixed TS
//     constant, but it is declared inside a .vue single-file component (or
//     otherwise not exported), so this script cannot import it without that
//     file exporting it, which is outside this change's file ownership.
//       - `common.weekdays.${day}` (WeeklyHoursGrid.vue's weekday loop).
//       - `officeLauncher.${tile.key}` (OfficeLauncher.vue's CORE_TILES).
//       - `search.groups.${...}` (SearchResultGroup.vue's GROUP_LABEL_KEYS).
//       - `productionSchedule.autoPlan.explain.facts.${field}`
//         (AutoPlanAlgorithmCards.vue's FACTS).
//       - `productionSchedule.autoPlan.planningLevelOptions.${value}`
//         (AutoPlanDialog.vue's PLANNING_LEVELS).
//       - `adminSettings.tabs.${tab.value}` (AdminSettingsView.vue's TABS).
//       - `adminSettings.mail.templates.groups.${group}`
//         (AdminSettingsTabMail.vue's TEMPLATE_GROUPS).
//       - `adminSettings.pdmSyncLog.runs.counts.${def.labelKey}`
//         (PdmSyncLogDialog.vue's count-column definitions).
//       - `madeItems.create.revision.predecessorStatus.options.${s}`
//         (MadeItemCreateForm.vue's PREDECESSOR_STATUS_OPTIONS).
//       - `production.lots.detail.forceStatus.${action}.*`
//         (LotForceStatusConfirmDialog.vue's own `action` prop union).
//
// (d) EXPORTED CONSTANT, UNSAFE IMPORT CHAIN. The array is exported and
//     would otherwise qualify, but its module also imports the vue-i18n
//     singleton (which touches `document` the moment it is loaded) or a
//     whole feature barrel, neither of which this plain Node script can run
//     without a DOM shim. Not worth the fragility for a CI gate.
//       - `boughtItems.units.*` (BOUGHT_ITEM_UNIT_CODES, in a module that
//         imports @/core/i18n for its formatUnit() function).
//       - `orders.mail.columns.*` (TABLE_COLUMN_KEYS, in a module that
//         imports the @/features/bought-items barrel).
//
// Separately, a number of the ~300 grep hits are not t() calls at all, just
// other backtick template strings the regex also matches: API path builders
// (`api.get(\`/orders/${id}/files/${fileId}\`)`), Map keys, a mail-template
// variable-insertion helper, and one JSDoc usage example. Those were read
// and discarded rather than treated as a family.

function permissionKey(perm: string): string {
  // Mirrors src/shared/utils/permissionLabels.ts's permissionLabel(): a
  // permission string like "write:bought_items" becomes "writeBoughtItems".
  return perm.replace(':', '_').replace(/_([a-z])/g, (_, c: string) => c.toUpperCase())
}

const lotPositionKinds = Object.keys(lotPositionKindSeverity) as LotPositionKind[]
const lotPositionStatuses = Object.keys(lotPositionStatusSeverity) as LotPositionStatus[]

// production.lots.positionStatus (and productionWip's copy) is keyed by the
// *display* status lotPositionStatusKey() derives from a (status, kind)
// pair, not by LotPositionStatus directly, see that function's own
// docstring for why pending/ordered_or_queued refine into more keys than
// the stored enum has members.
const positionDisplayStatuses = new Set<string>()
for (const status of lotPositionStatuses) {
  for (const kind of [...lotPositionKinds, null]) {
    positionDisplayStatuses.add(lotPositionStatusKey(status, kind))
  }
}

const productionOrderStatuses = Object.keys(productionOrderStatusSeverity) as ProductionOrderStatus[]
const productionOrderPriorities = Object.keys(
  productionOrderPrioritySeverity,
) as ProductionOrderPriority[]

// Bought, made and source items all share this catalogue status enum, see
// catalogueStatus.ts's own docstring. The lot record's item/source status
// display reuses it too.
const catalogueStatuses = Object.keys(catalogueStatusSeverity)

type DynamicKeyFamily = { name: string; keys: string[] }

const dynamicKeyFamilies: DynamicKeyFamily[] = [
  {
    name: 'production.lots.status.* (LOT_STATUSES)',
    keys: LOT_STATUSES.map((s) => `production.lots.status.${s}`),
  },
  {
    name: 'production.lots.priority.* (LOT_PRIORITIES)',
    keys: LOT_PRIORITIES.map((p) => `production.lots.priority.${p}`),
  },
  {
    name: 'production.lots.positionKind.* / productionWip.positionKind.* (LotPositionKind)',
    keys: lotPositionKinds.flatMap((k) => [
      `production.lots.positionKind.${k}`,
      `productionWip.positionKind.${k}`,
    ]),
  },
  {
    name: 'production.lots.positionStatus.* / productionWip.positionStatus.* (lotPositionStatusKey outputs)',
    keys: [...positionDisplayStatuses].flatMap((k) => [
      `production.lots.positionStatus.${k}`,
      `productionWip.positionStatus.${k}`,
    ]),
  },
  {
    name: 'boughtItems.demands.status.* / madeItems.demands.status.* / sourceItems.demands.status.* (DEMAND_STATUSES)',
    keys: DEMAND_STATUSES.flatMap((s) => [
      `boughtItems.demands.status.${s}`,
      `madeItems.demands.status.${s}`,
      `sourceItems.demands.status.${s}`,
    ]),
  },
  {
    name: 'settings.users.permissions.* (Permission.ALL)',
    keys: Permission.ALL.map((p) => `settings.users.permissions.${permissionKey(p)}`),
  },
  {
    name: 'settings.users.authProviders.* (AUTH_PROVIDERS)',
    keys: AUTH_PROVIDERS.map((p) => `settings.users.authProviders.${p}`),
  },
  {
    name: 'resources.projects.status.* / production.lots.detail.record.project.statusValues.* (PROJECT_STATUSES)',
    keys: PROJECT_STATUSES.flatMap((s) => [
      `resources.projects.status.${s}`,
      `production.lots.detail.record.project.statusValues.${s}`,
    ]),
  },
  {
    name: 'todo.categories.* (TODO_CATEGORIES)',
    keys: TODO_CATEGORIES.map((c) => `todo.categories.${c}`),
  },
  {
    name: 'productionAssessment.complexity.* / productionAssessment.rubric.* (MANUFACTURING_COMPLEXITIES)',
    keys: MANUFACTURING_COMPLEXITIES.flatMap((c) => [
      `productionAssessment.complexity.${c}`,
      `productionAssessment.rubric.${c}`,
    ]),
  },
  {
    name: 'productionPlanning.resolution.* (GANTT_RESOLUTIONS)',
    keys: GANTT_RESOLUTIONS.map((r) => `productionPlanning.resolution.${r}`),
  },
  {
    name: 'production.lots.orderStatus.* / productionQueue.status.* (ProductionOrderStatus)',
    keys: productionOrderStatuses.flatMap((s) => [
      `production.lots.orderStatus.${s}`,
      `productionQueue.status.${s}`,
    ]),
  },
  {
    name: 'productionQueue.priority.* (ProductionOrderPriority)',
    keys: productionOrderPriorities.map((p) => `productionQueue.priority.${p}`),
  },
  {
    name: 'adminSettings.solidworksPdm.pdm.sync.documentCategories.categories.* (PDM_DOCUMENT_CATEGORIES)',
    keys: PDM_DOCUMENT_CATEGORIES.map(
      (c) => `adminSettings.solidworksPdm.pdm.sync.documentCategories.categories.${c}`,
    ),
  },
  {
    name: 'timeTracking.dayStatus.* (TIME_TRACKING_DAY_STATUSES)',
    keys: TIME_TRACKING_DAY_STATUSES.map((s) => `timeTracking.dayStatus.${s}`),
  },
  {
    name: 'timeTracking.empty.* / accountMe.timeTracking.invalid.* (TIME_TRACKING_INVALID_REASONS)',
    keys: TIME_TRACKING_INVALID_REASONS.flatMap((r) =>
      r === 'missing'
        ? [`timeTracking.empty.${r}`]
        : [`timeTracking.empty.${r}`, `accountMe.timeTracking.invalid.${r}`],
    ),
  },
  {
    name: 'adminSettings.pdmReconciliation.categories.*.label / .description (PDM_RECONCILIATION_CATEGORIES)',
    keys: PDM_RECONCILIATION_CATEGORIES.flatMap((c) => [
      `adminSettings.pdmReconciliation.categories.${c}.label`,
      `adminSettings.pdmReconciliation.categories.${c}.description`,
    ]),
  },
  {
    name: 'boughtItems.catalogue.status.* / sourceItems.catalogue.status.* / madeItems.catalogue.status.* / production.lots.detail.record.item.statusValues.* / production.lots.detail.record.source.statusValues.* (catalogueStatusSeverity)',
    keys: catalogueStatuses.flatMap((s) => [
      `boughtItems.catalogue.status.${s}`,
      `sourceItems.catalogue.status.${s}`,
      `madeItems.catalogue.status.${s}`,
      `production.lots.detail.record.item.statusValues.${s}`,
      `production.lots.detail.record.source.statusValues.${s}`,
    ]),
  },
]

const dynamicKeyCount = dynamicKeyFamilies.reduce((sum, family) => sum + family.keys.length, 0)

const dynamicMissingInDe = dynamicKeyFamilies.flatMap(({ name, keys }) =>
  keys.filter((key) => !deKeys.has(key)).map((key) => ({ name, key })),
)
const dynamicMissingInEn = dynamicKeyFamilies.flatMap(({ name, keys }) =>
  keys.filter((key) => !enKeys.has(key)).map((key) => ({ name, key })),
)

if (dynamicMissingInDe.length > 0) {
  console.error(
    `\n✖ ${dynamicMissingInDe.length} dynamically-built key(s) missing in de-AT, one of the ` +
      `enum members listed below has no German translation:`,
  )
  dynamicMissingInDe.forEach(({ name, key }) => console.error(`  ${key}  [${name}]`))
}

if (dynamicMissingInEn.length > 0) {
  console.error(
    `\n✖ ${dynamicMissingInEn.length} dynamically-built key(s) missing in en-GB, one of the ` +
      `enum members listed below has no matching translation:`,
  )
  dynamicMissingInEn.forEach(({ name, key }) => console.error(`  ${key}  [${name}]`))
}

if (dynamicMissingInDe.length > 0 || dynamicMissingInEn.length > 0) {
  console.error('')
  process.exit(1)
}

// Copy must address the user informally. Each locale lists the words of its
// formal address under localeRules.formalAddressWords (English has none), so
// the words themselves stay in the translation files. The de-AT strings in
// this allowlist contain such a word grammatically but do not address the
// user, so they are exempt.
const formalAddressAllowlist = new Set<string>([
  // The pronoun refers back to the LDAP accounts (third-person plural), not to the user.
  'settings.users.fields.authProviderHint',
  // The pronoun refers to two-factor authentication (third person), not to the user.
  'account.twoFactor.systemUserMandatory',
  // The pronoun refers to the order (third person), not to the user.
  'orders.actions.submitConfirm',
])

const formalAddressLocales: { name: string; messages: Messages; words: readonly string[] }[] = [
  { name: 'en-GB', messages: enGB as Messages, words: enGB.localeRules.formalAddressWords },
  { name: 'de-AT', messages: deAT as Messages, words: deAT.localeRules.formalAddressWords },
]

const formalAddressViolations = formalAddressLocales.flatMap(({ name, messages, words }) => {
  if (words.length === 0) return []
  const pattern = new RegExp(`\\b(${words.join('|')})\\b`)
  return flattenLeaves(messages)
    .filter(({ key, value }) => !formalAddressAllowlist.has(key) && pattern.test(value))
    .map((entry) => ({ name, ...entry }))
})

if (formalAddressViolations.length > 0) {
  console.error(
    `\n✖ ${formalAddressViolations.length} string(s) use the formal address instead of the ` +
      `informal one:`,
  )
  formalAddressViolations.forEach(({ name, key, value }) => console.error(`  ${name} ${key}: ${value}`))
  console.error('')
  process.exit(1)
}

console.log(
  `✓ i18n parity: en-GB has ${enKeys.size} keys, de-AT has ${deKeys.size} keys, ` +
    `${dynamicKeyCount} dynamically-built keys across ${dynamicKeyFamilies.length} families checked, ` +
    `${enMain.namespaces.length} namespaces in matching files, no gaps in either locale.`,
)
