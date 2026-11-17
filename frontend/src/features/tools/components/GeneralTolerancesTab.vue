<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAppToast } from '@/core/composables/useAppToast'
import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { localeTag } from '@/core/utils/dates'
import { degreesAndMinutes, lookup, rangeIndexOf } from '../utils/iso2768/lookup'
import type { LookupResult } from '../utils/iso2768/lookup'
import {
  ANGULAR,
  BROKEN_EDGES,
  CIRCULAR_RUN_OUT,
  GEOMETRIC_CLASSES,
  LINEAR,
  LINEAR_CLASSES,
  PERPENDICULARITY,
  STRAIGHTNESS_FLATNESS,
  SYMMETRY,
} from '../utils/iso2768/tables'
import type { GeometricClass, LinearClass, SizeRange, ToleranceTable } from '../utils/iso2768/tables'
import ToolReferenceTable from './ToolReferenceTable.vue'
import type { ToolReferenceRow } from './ToolReferenceTable.vue'
import { publishToolState, useInitialToolInputs } from '../composables/useToolState'
import { parseSavedSize, savedString } from '../utils/savedInputs'
import { generalTolerancesSnapshot } from '../utils/iso2768/snapshot'

type GeometricChoice = GeometricClass | 'none'

const DEFAULT_SIZE = 25
const DEFAULT_LINEAR: LinearClass = 'm'
const DEFAULT_GEOMETRIC: GeometricChoice = 'K'
const MAX_SIZE = 4000

const { t } = useI18n()
const toast = useAppToast()
const { formatNumber } = useLocaleFormat()

/**
 * Reads the inputs of a saved calculation. A missing part falls back to its
 * default silently, an invalid one falls back too and the user is told once.
 */
function readInputs(saved: Record<string, string> | null) {
  let invalid = false
  const rawSize = savedString(saved?.d)
  const rawLinear = savedString(saved?.linear)
  const rawGeometric = savedString(saved?.geometric)

  const savedSize = parseSavedSize(rawSize, DEFAULT_SIZE, MAX_SIZE)
  const size = savedSize.size
  if (savedSize.invalid) invalid = true

  let linear = DEFAULT_LINEAR
  if (rawLinear !== null) {
    if ((LINEAR_CLASSES as readonly string[]).includes(rawLinear)) linear = rawLinear as LinearClass
    else invalid = true
  }

  let geometric: GeometricChoice = DEFAULT_GEOMETRIC
  if (rawGeometric !== null) {
    if (rawGeometric === 'none' || (GEOMETRIC_CLASSES as readonly string[]).includes(rawGeometric)) {
      geometric = rawGeometric as GeometricChoice
    } else invalid = true
  }

  return { size, linear, geometric, invalid }
}

const initial = readInputs(useInitialToolInputs())
if (initial.invalid) toast.warn('', t('tools.calculations.errors.invalidInputs'))

const size = ref<number | null>(initial.size)
const linearClass = ref<LinearClass>(initial.linear)
const geometricClass = ref<GeometricChoice>(initial.geometric)

const designation = computed(
  () => `ISO 2768-${linearClass.value}${geometricClass.value === 'none' ? '' : geometricClass.value}`,
)

const linearOptions = computed(() =>
  LINEAR_CLASSES.map((value) => ({ value, name: t(`tools.generalTolerances.linearClasses.${value}`) })),
)
const geometricOptions = computed(() => [
  ...GEOMETRIC_CLASSES.map((value) => ({ value, name: '' })),
  { value: 'none' as const, name: t('tools.generalTolerances.geometricNone') },
])

// ── Formatting ────────────────────────────────────────────────────────────

function num(value: number): string {
  return formatNumber(value, { maximumFractionDigits: 3 })
}

function plusMinusMm(value: number): string {
  return `±${num(value)} mm`
}

function angle(minutes: number): string {
  const split = degreesAndMinutes(minutes)
  return split.minutes === 0 ? `±${split.degrees}°` : `±${split.degrees}° ${split.minutes}′`
}

function tolerance(value: number): string {
  return `${num(value)} mm`
}

function rangeLabel(range: SizeRange): string {
  if (range.includeFrom && range.to !== null) {
    return t('tools.generalTolerances.ranges.fromTo', { from: num(range.from), to: num(range.to) })
  }
  if (range.to === null) return t('tools.generalTolerances.ranges.over', { from: num(range.from) })
  if (range.from === 0) return t('tools.generalTolerances.ranges.upTo', { to: num(range.to) })
  return t('tools.generalTolerances.ranges.overTo', { from: num(range.from), to: num(range.to) })
}

function reason<C extends string>(result: LookupResult, table: ToleranceTable<C>, cls: string): string {
  if (result.ok) return ''
  if (result.reason === 'belowRange') {
    return t('tools.generalTolerances.reasons.belowRange', { min: num(table.ranges[0]?.from ?? 0) })
  }
  if (result.reason === 'aboveRange') {
    const last = table.ranges[table.ranges.length - 1]
    return t('tools.generalTolerances.reasons.aboveRange', { max: num(last?.to ?? 0) })
  }
  if (result.reason === 'notDefined') return t('tools.generalTolerances.reasons.notDefined', { cls })
  return t('tools.generalTolerances.reasons.invalidSize')
}

// ── Results for the entered size ──────────────────────────────────────────

interface ResultRow {
  key: string
  label: string
  value: string | null
  hint: string
}

const sizeValid = computed(() => size.value !== null && size.value > 0)

function resultRow<C extends string>(
  key: string,
  table: ToleranceTable<C>,
  cls: C,
  format: (value: number) => string,
): ResultRow {
  const result = lookup(table, cls, size.value ?? Number.NaN)
  return {
    key,
    label: t(`tools.generalTolerances.items.${key}`),
    value: result.ok ? format(result.value) : null,
    hint: reason(result, table, cls),
  }
}

const linearRows = computed<ResultRow[]>(() => {
  const cls = linearClass.value
  const n = size.value ?? Number.NaN
  const linear = lookup(LINEAR, cls, n)
  const rows: ResultRow[] = [resultRow('linear', LINEAR, cls, plusMinusMm)]
  if (linear.ok) {
    rows.push(
      { key: 'maxSize', label: t('tools.generalTolerances.items.maxSize'), value: `${num(n + linear.value)} mm`, hint: '' },
      { key: 'minSize', label: t('tools.generalTolerances.items.minSize'), value: `${num(n - linear.value)} mm`, hint: '' },
    )
  }
  rows.push(resultRow('brokenEdge', BROKEN_EDGES, cls, plusMinusMm))
  rows.push(resultRow('angular', ANGULAR, cls, angle))
  return rows
})

const geometricRows = computed<ResultRow[]>(() => {
  const cls = geometricClass.value
  if (cls === 'none') return []
  return [
    resultRow('straightnessFlatness', STRAIGHTNESS_FLATNESS, cls, tolerance),
    resultRow('perpendicularity', PERPENDICULARITY, cls, tolerance),
    resultRow('symmetry', SYMMETRY, cls, tolerance),
    resultRow('circularRunOut', CIRCULAR_RUN_OUT, cls, tolerance),
  ]
})

const resultCards = computed(() => [
  {
    key: 'linear',
    title: t('tools.generalTolerances.linearCard'),
    cls: t('tools.generalTolerances.classLabel', { cls: linearClass.value }),
    rows: linearRows.value,
    empty: '',
  },
  {
    key: 'geometric',
    title: t('tools.generalTolerances.geometricCard'),
    cls:
      geometricClass.value === 'none'
        ? ''
        : t('tools.generalTolerances.classLabel', { cls: geometricClass.value }),
    rows: geometricRows.value,
    empty: geometricClass.value === 'none' ? t('tools.generalTolerances.noGeometricClass') : '',
  },
])

// ── Reference tables ──────────────────────────────────────────────────────

function tableRows<C extends string>(
  table: ToleranceTable<C>,
  classes: readonly C[],
  label: (cls: C) => string,
  format: (value: number) => string,
): ToolReferenceRow[] {
  return classes.map((cls) => ({
    key: cls,
    label: label(cls),
    cells: table.values[cls].map((value) => (value === null ? '–' : format(value))),
  }))
}

function activeColumn(ranges: readonly SizeRange[]): number | null {
  return sizeValid.value ? rangeIndexOf(ranges, size.value as number) : null
}

const linearLabel = (cls: LinearClass) => `${cls} (${t(`tools.generalTolerances.linearClasses.${cls}`)})`
const geometricLabel = (cls: GeometricClass) => cls
const plusMinus = (value: number) => `±${num(value)}`

const linearTables = computed(() => [
  {
    key: 'linear',
    title: t('tools.generalTolerances.tables.linear'),
    unit: t('tools.generalTolerances.tables.unitMm'),
    columns: LINEAR.ranges.map(rangeLabel),
    rows: tableRows(LINEAR, LINEAR_CLASSES, linearLabel, plusMinus),
    activeColumn: activeColumn(LINEAR.ranges),
    wide: true,
  },
  {
    key: 'brokenEdges',
    title: t('tools.generalTolerances.tables.brokenEdges'),
    unit: t('tools.generalTolerances.tables.unitMm'),
    columns: BROKEN_EDGES.ranges.map(rangeLabel),
    rows: tableRows(BROKEN_EDGES, LINEAR_CLASSES, linearLabel, plusMinus),
    activeColumn: activeColumn(BROKEN_EDGES.ranges),
    wide: false,
  },
  {
    key: 'angular',
    title: t('tools.generalTolerances.tables.angular'),
    unit: t('tools.generalTolerances.tables.unitAngle'),
    columns: ANGULAR.ranges.map(rangeLabel),
    rows: tableRows(ANGULAR, LINEAR_CLASSES, linearLabel, angle),
    activeColumn: activeColumn(ANGULAR.ranges),
    wide: false,
  },
])

const geometricTables = computed(() => [
  {
    key: 'straightnessFlatness',
    title: t('tools.generalTolerances.tables.straightnessFlatness'),
    unit: t('tools.generalTolerances.tables.unitLength'),
    columns: STRAIGHTNESS_FLATNESS.ranges.map(rangeLabel),
    rows: tableRows(STRAIGHTNESS_FLATNESS, GEOMETRIC_CLASSES, geometricLabel, num),
    activeColumn: activeColumn(STRAIGHTNESS_FLATNESS.ranges),
    wide: true,
  },
  {
    key: 'perpendicularity',
    title: t('tools.generalTolerances.tables.perpendicularity'),
    unit: t('tools.generalTolerances.tables.unitShorterSide'),
    columns: PERPENDICULARITY.ranges.map(rangeLabel),
    rows: tableRows(PERPENDICULARITY, GEOMETRIC_CLASSES, geometricLabel, num),
    activeColumn: activeColumn(PERPENDICULARITY.ranges),
    wide: false,
  },
  {
    key: 'symmetry',
    title: t('tools.generalTolerances.tables.symmetry'),
    unit: t('tools.generalTolerances.tables.unitShorterFeature'),
    columns: SYMMETRY.ranges.map(rangeLabel),
    rows: tableRows(SYMMETRY, GEOMETRIC_CLASSES, geometricLabel, num),
    activeColumn: activeColumn(SYMMETRY.ranges),
    wide: false,
  },
  {
    key: 'circularRunOut',
    title: t('tools.generalTolerances.tables.circularRunOut'),
    unit: t('tools.generalTolerances.tables.unitRunOut'),
    columns: [t('tools.generalTolerances.tables.anySize')],
    rows: tableRows(CIRCULAR_RUN_OUT, GEOMETRIC_CLASSES, geometricLabel, num),
    activeColumn: sizeValid.value ? 0 : null,
    wide: false,
  },
])

// ── Saving ────────────────────────────────────────────────────────────────

const inputs = computed(() => ({
  d: size.value === null ? '' : String(size.value),
  linear: linearClass.value,
  geometric: geometricClass.value,
}))

publishToolState(() => ({
  inputs: inputs.value,
  results: generalTolerancesSnapshot(designation.value, size.value, linearClass.value, geometricClass.value),
  title: `${designation.value}, ${size.value === null ? '' : num(size.value)} mm`,
}))
</script>

<template>
  <div class="gt">
    <section class="gt-panel gt-inputs">
      <span class="gt-code" data-testid="gt-designation">{{ designation }}</span>
      <div class="gt-field">
        <label for="gt-size" class="gt-label">{{ t('tools.generalTolerances.nominalSize') }}</label>
        <InputNumber
          v-model="size"
          input-id="gt-size"
          :min="0"
          :max="MAX_SIZE"
          :min-fraction-digits="0"
          :max-fraction-digits="3"
          :locale="localeTag()"
          suffix=" mm"
          data-testid="gt-size"
          class="gt-size-input"
        />
      </div>
      <div class="gt-field">
        <span id="gt-linear-label" class="gt-label">{{ t('tools.generalTolerances.linearClass') }}</span>
        <SelectButton
          v-model="linearClass"
          :options="linearOptions"
          option-value="value"
          option-label="name"
          :allow-empty="false"
          aria-labelledby="gt-linear-label"
          data-testid="gt-linear-class"
        >
          <template #option="{ option }">
            <span class="gt-option"><strong>{{ option.value }}</strong> {{ option.name }}</span>
          </template>
        </SelectButton>
      </div>
      <div class="gt-field">
        <span id="gt-geometric-label" class="gt-label">{{ t('tools.generalTolerances.geometricClass') }}</span>
        <SelectButton
          v-model="geometricClass"
          :options="geometricOptions"
          option-value="value"
          option-label="name"
          :allow-empty="false"
          aria-labelledby="gt-geometric-label"
          data-testid="gt-geometric-class"
        >
          <template #option="{ option }">
            <span class="gt-option">
              <strong v-if="option.value !== 'none'">{{ option.value }}</strong>
              <template v-else>{{ option.name }}</template>
            </span>
          </template>
        </SelectButton>
      </div>
    </section>

    <div class="gt-results">
      <section v-for="card in resultCards" :key="card.key" class="gt-panel gt-card" :data-testid="`gt-card-${card.key}`">
        <header class="gt-card-header">
          <h3 class="gt-card-title">{{ card.title }}</h3>
          <span v-if="card.cls" class="gt-card-class">{{ card.cls }}</span>
        </header>
        <Message v-if="!sizeValid" severity="warn" :closable="false">
          {{ t('tools.generalTolerances.reasons.invalidSize') }}
        </Message>
        <p v-else-if="card.empty" class="gt-card-empty">{{ card.empty }}</p>
        <dl v-else class="gt-rows">
          <div v-for="row in card.rows" :key="row.key" class="gt-row">
            <dt>{{ row.label }}</dt>
            <dd v-if="row.value !== null" class="gt-row-value" :data-testid="`gt-${row.key}`">{{ row.value }}</dd>
            <dd v-else class="gt-row-hint" :data-testid="`gt-${row.key}`">{{ row.hint }}</dd>
          </div>
        </dl>
      </section>
    </div>

    <section class="gt-panel gt-details" data-testid="gt-details">
      <h3 class="gt-section-title">{{ t('tools.generalTolerances.tables.linearTitle') }}</h3>
      <div class="gt-tables">
        <ToolReferenceTable
          v-for="table in linearTables"
          :key="table.key"
          :class="{ 'gt-table--wide': table.wide }"
          :style="{ '--gt-weight': table.columns.length + 1 }"
          :table-key="table.key"
          :title="table.title"
          :unit="table.unit"
          :row-header="t('tools.generalTolerances.tables.classColumn')"
          :columns="table.columns"
          :rows="table.rows"
          :active-row="linearClass"
          :active-column="table.activeColumn"
        />
      </div>
      <h3 class="gt-section-title">{{ t('tools.generalTolerances.tables.geometricTitle') }}</h3>
      <div class="gt-tables">
        <ToolReferenceTable
          v-for="table in geometricTables"
          :key="table.key"
          :class="{ 'gt-table--wide': table.wide }"
          :style="{ '--gt-weight': table.columns.length + 1 }"
          :table-key="table.key"
          :title="table.title"
          :unit="table.unit"
          :row-header="t('tools.generalTolerances.tables.classColumn')"
          :columns="table.columns"
          :rows="table.rows"
          :active-row="geometricClass === 'none' ? null : geometricClass"
          :active-column="table.activeColumn"
        />
      </div>
      <p class="gt-footnote">{{ t('tools.generalTolerances.footnote') }}</p>
    </section>
  </div>
</template>

<style scoped lang="scss">
// Like the fit calculator: inputs and result cards stay in view, the tables
// below take the remaining height and scroll on their own. On a narrow screen
// everything stacks and the whole tab scrolls.
.gt {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);

  > :not(.gt-details) {
    flex-shrink: 0;
  }
}

.gt-panel {
  padding: var(--space-3) var(--space-4);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.gt-inputs {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--space-5);
}

.gt-code {
  min-width: 10rem;
  line-height: 2.5rem;
  font-size: var(--font-size-xl);
  font-weight: 600;
  white-space: nowrap;
}

.gt-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.gt-label {
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--p-text-muted-color);
}

.gt-size-input :deep(input) {
  width: 8rem;
}

.gt-option {
  white-space: nowrap;
}

.gt-results {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(20rem, 1fr));
  gap: var(--space-2);
}

.gt-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-width: 0;
}

.gt-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.gt-card-title {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
}

.gt-card-class {
  margin-left: auto;
  font-weight: 600;
}

.gt-card-empty {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.gt-rows {
  margin: 0;
  display: flex;
  flex-direction: column;
}

.gt-row {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  border-top: 1px solid var(--p-content-border-color);

  dt {
    flex: 1;
    color: var(--p-text-muted-color);
  }

  dd {
    margin: 0;
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
}

.gt-row-value {
  font-weight: 500;
}

.gt-row-hint {
  font-size: var(--font-size-sm);
  color: var(--p-orange-500);
}

.gt-details {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.gt-section-title {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
}

.gt-tables {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(22rem, 1fr));
  gap: var(--space-2);
}

.gt-table--wide {
  grid-column: 1 / -1;
}

// On a wide screen each standard's tables share one row, every table as wide
// as its share of the columns (ranges plus the class column), so a five-range
// table gets more room than a one-range one and no row is left half empty.
@media (min-width: $bp-2xl) {
  .gt-tables {
    display: flex;
    align-items: stretch;
  }

  .gt-tables > * {
    flex: var(--gt-weight) 1 0;
  }
}

.gt-footnote {
  margin: 0;
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

@media (max-width: $bp-lg) {
  .gt {
    height: auto;
  }

  .gt-details {
    overflow-y: visible;
  }
}
</style>
