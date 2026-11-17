<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAppToast } from '@/core/composables/useAppToast'
import { useThreadFormat, useThreadReferenceSections } from '../composables/useThreadReferenceSections'
import {
  CAP_SCREW_COUNTERBORES,
  CLEARANCE_HOLES,
  COUNTERSINKS_ISO_10642,
  COUNTERSINKS_ISO_15065,
  HEX_COUNTERBORES,
} from '../utils/threads/holes'
import {
  COARSE_THREADS,
  FINE_THREADS,
  findThread,
  threadGeometry,
  WIDTH_ACROSS_FLATS,
} from '../utils/threads/metric'
import type { MetricThread } from '../utils/threads/metric'
import { PROPERTY_CLASSES, tighteningFor } from '../utils/threads/tightening'
import type { PropertyClass } from '../utils/threads/tightening'
import HoleSketch from './HoleSketch.vue'
import ThreadProfileSketch from './ThreadProfileSketch.vue'
import TighteningSketch from './TighteningSketch.vue'
import ToolReferenceTable from './ToolReferenceTable.vue'
import { publishToolState, useInitialToolInputs } from '../composables/useToolState'
import { savedString } from '../utils/savedInputs'

const DEFAULT_THREAD = 'M8'
const DEFAULT_CLASS: PropertyClass = '8.8'

const { t } = useI18n()
const toast = useAppToast()

/**
 * Reads the inputs of a saved calculation. A missing part falls back to its
 * default silently, an invalid one falls back too and the user is told once.
 */
function readInputs(saved: Record<string, string> | null) {
  let invalid = false
  const rawThread = savedString(saved?.thread)
  const rawClass = savedString(saved?.class)

  let thread = DEFAULT_THREAD
  if (rawThread !== null) {
    if (findThread(rawThread)) thread = rawThread
    else invalid = true
  }
  let propertyClass = DEFAULT_CLASS
  if (rawClass !== null) {
    if ((PROPERTY_CLASSES as readonly string[]).includes(rawClass)) propertyClass = rawClass as PropertyClass
    else invalid = true
  }
  return { thread, propertyClass, invalid }
}

const initial = readInputs(useInitialToolInputs())
if (initial.invalid) toast.warn('', t('tools.calculations.errors.invalidInputs'))

const threadCode = ref(initial.thread)
const propertyClass = ref<PropertyClass>(initial.propertyClass)

const thread = computed<MetricThread>(
  () => findThread(threadCode.value) ?? (findThread(DEFAULT_THREAD) as MetricThread),
)

const { num, fixed3, mm, area, threadLabel } = useThreadFormat()

const threadOptions = computed(() => [
  {
    label: t('tools.threads.coarse'),
    items: COARSE_THREADS.map((th) => ({ value: th.code, label: threadLabel(th) })),
  },
  {
    label: t('tools.threads.fine'),
    items: FINE_THREADS.map((th) => ({ value: th.code, label: threadLabel(th) })),
  },
])

// ── Results for the selected thread ───────────────────────────────────────

interface ResultRow {
  key: string
  label: string
  value: string | null
  emphasis?: boolean
}

const geometry = computed(() => threadGeometry(thread.value.d, thread.value.pitch, thread.value.fine))

const threadRows = computed<ResultRow[]>(() => {
  const g = geometry.value
  const item = (key: string) => t(`tools.threads.items.${key}`)
  const rows: ResultRow[] = [
    { key: 'pitch', label: item('pitch'), value: mm(thread.value.pitch) },
    { key: 'pitchDiameter', label: item('pitchDiameter'), value: `${fixed3(g.d2)} mm` },
    { key: 'minorExternal', label: item('minorExternal'), value: `${fixed3(g.d3)} mm` },
    { key: 'minorInternal', label: item('minorInternal'), value: `${fixed3(g.D1)} mm` },
    { key: 'depthExternal', label: item('depthExternal'), value: `${fixed3(g.h3)} mm` },
    { key: 'depthInternal', label: item('depthInternal'), value: `${fixed3(g.H1)} mm` },
    { key: 'stressArea', label: item('stressArea'), value: `${area(g.stressArea)} mm²` },
    { key: 'tapDrill', label: item('tapDrill'), value: `Ø ${mm(g.tapDrill)}`, emphasis: true },
  ]
  const waf = thread.value.fine ? undefined : WIDTH_ACROSS_FLATS[thread.value.d]
  if (waf !== undefined) rows.push({ key: 'widthAcrossFlats', label: item('widthAcrossFlats'), value: mm(waf) })
  return rows
})

const holeRows = computed<ResultRow[]>(() => {
  const d = thread.value.d
  const item = (key: string) => t(`tools.threads.items.${key}`)
  const clearance = CLEARANCE_HOLES[d]
  const cap = CAP_SCREW_COUNTERBORES[d]
  const capDiameter = cap?.series[0] ?? null
  const capDepth = cap?.depth.iso4762 ?? null
  const hex = HEX_COUNTERBORES[d]
  const socket = COUNTERSINKS_ISO_10642[d]
  const slotted = COUNTERSINKS_ISO_15065[d]
  return [
    { key: 'clearanceFine', label: item('clearanceFine'), value: clearance ? `Ø ${mm(clearance[0])}` : null },
    {
      key: 'clearanceMedium',
      label: item('clearanceMedium'),
      value: clearance ? `Ø ${mm(clearance[1])}` : null,
      emphasis: true,
    },
    { key: 'clearanceCoarse', label: item('clearanceCoarse'), value: clearance ? `Ø ${mm(clearance[2])}` : null },
    {
      key: 'counterboreCapScrew',
      label: item('counterboreCapScrew'),
      value: capDiameter !== null && capDepth !== null ? `Ø ${num(capDiameter)} × ${mm(capDepth)}` : null,
    },
    {
      key: 'counterboreHex',
      label: item('counterboreHex'),
      value: hex ? `Ø ${num(hex.series[0])} × ${mm(hex.depth)}` : null,
    },
    {
      key: 'countersinkSocket',
      label: item('countersinkSocket'),
      value: socket ? `Ø ${mm(socket.d2)}, 90°` : null,
    },
    {
      key: 'countersinkSlotted',
      label: item('countersinkSlotted'),
      value: slotted ? `Ø ${num(slotted.d2Min)} … ${mm(slotted.d2Max)}, 90°` : null,
    },
  ]
})

const classIndex = computed(() => PROPERTY_CLASSES.indexOf(propertyClass.value))
const tightening = computed(() =>
  thread.value.fine ? undefined : tighteningFor(thread.value.d, thread.value.pitch),
)

const tighteningRows = computed<ResultRow[]>(() => {
  const row = tightening.value
  if (!row) return []
  const i = classIndex.value
  return [
    {
      key: 'torque',
      label: t('tools.threads.items.torque'),
      value: `${num(row.torque[i] as number, 2)} Nm`,
      emphasis: true,
    },
    { key: 'preload', label: t('tools.threads.items.preload'), value: `${num(row.preload[i] as number, 2)} kN` },
  ]
})

const tighteningEmpty = computed(() =>
  thread.value.fine ? t('tools.threads.tighteningCoarseOnly') : t('tools.threads.notListed'),
)

const sections = useThreadReferenceSections({
  threadCode,
  thread,
  classIndex,
  hasTightening: computed(() => tightening.value !== undefined),
})

// The reference card shows one section at a time; each table carries the
// sketch that explains the symbols in its header.
type SectionKey = 'threads' | 'holes' | 'tightening'
const activeSection = ref<SectionKey>('threads')
const sectionOptions = computed(() =>
  sections.value.map((section) => ({ value: section.key as SectionKey, label: section.title })),
)
const currentSection = computed(
  () => sections.value.find((section) => section.key === activeSection.value) ?? sections.value[0],
)

// ── URL and sharing ───────────────────────────────────────────────────────

const inputs = computed(() => ({ thread: threadCode.value, class: propertyClass.value }))

// Dimensions in mm, torque in Nm and preload in kN, as tabulated; the saved
// snapshot must not depend on the viewer's number format.
publishToolState(() => {
  const g = geometry.value
  const row = tightening.value
  const i = classIndex.value
  return {
    inputs: inputs.value,
    results: {
      thread: thread.value.code,
      pitch: thread.value.pitch,
      fine: thread.value.fine,
      pitchDiameter: g.d2,
      minorExternal: g.d3,
      minorInternal: g.D1,
      stressArea: g.stressArea,
      tapDrill: g.tapDrill,
      clearanceHoles: CLEARANCE_HOLES[thread.value.d] ?? null,
      propertyClass: propertyClass.value,
      torque: row ? (row.torque[i] ?? null) : null,
      preload: row ? (row.preload[i] ?? null) : null,
    },
    title: `${threadLabel(thread.value)}, ${propertyClass.value}`,
  }
})

const cards = computed(() => [
  { key: 'thread', title: t('tools.threads.threadCard'), tag: threadLabel(thread.value), rows: threadRows.value, empty: '' },
  { key: 'holes', title: t('tools.threads.holesCard'), tag: `M${num(thread.value.d)}`, rows: holeRows.value, empty: '' },
  {
    key: 'tightening',
    title: t('tools.threads.tighteningCard'),
    tag: t('tools.threads.classLabel', { cls: propertyClass.value }),
    rows: tighteningRows.value,
    empty: tighteningRows.value.length === 0 ? tighteningEmpty.value : '',
  },
])
</script>

<template>
  <div class="th">
    <section class="th-panel th-inputs">
      <span class="th-code" data-testid="th-designation">{{ threadLabel(thread) }}</span>
      <div class="th-field">
        <span id="th-thread-label" class="th-label">{{ t('tools.threads.thread') }}</span>
        <Select
          v-model="threadCode"
          :options="threadOptions"
          option-group-label="label"
          option-group-children="items"
          option-label="label"
          option-value="value"
          filter
          aria-labelledby="th-thread-label"
          data-testid="th-thread"
          class="th-thread-select"
        />
      </div>
      <div class="th-field">
        <span id="th-class-label" class="th-label">{{ t('tools.threads.propertyClass') }}</span>
        <SelectButton
          v-model="propertyClass"
          :options="[...PROPERTY_CLASSES]"
          :allow-empty="false"
          aria-labelledby="th-class-label"
          data-testid="th-class"
        />
      </div>
    </section>

    <div class="th-results">
      <section v-for="card in cards" :key="card.key" class="th-panel th-card" :data-testid="`th-card-${card.key}`">
        <header class="th-card-header">
          <h3 class="th-card-title">{{ card.title }}</h3>
          <span class="th-card-tag">{{ card.tag }}</span>
        </header>
        <p v-if="card.empty" class="th-card-empty">{{ card.empty }}</p>
        <dl v-else class="th-rows">
          <div v-for="row in card.rows" :key="row.key" class="th-row">
            <dt>{{ row.label }}</dt>
            <dd
              :class="row.value === null ? 'th-row-missing' : { 'th-row-value': true, 'th-row-value--emphasis': row.emphasis }"
              :data-testid="`th-${row.key}`"
            >
              {{ row.value ?? t('tools.threads.notListed') }}
            </dd>
          </div>
        </dl>
        <small v-if="card.key === 'tightening'" class="th-card-note">{{ t('tools.threads.tighteningNote') }}</small>
      </section>
    </div>

    <section class="th-panel th-details" data-testid="th-details">
      <SelectButton
        v-model="activeSection"
        :options="sectionOptions"
        option-label="label"
        option-value="value"
        :allow-empty="false"
        :aria-label="t('tools.threads.tables.sectionSwitch')"
        data-testid="th-section"
        class="th-section-switch"
      />
      <!-- Every table key is unique across the sections, so switching section
           mounts fresh tables, and each opens scrolled to the selected thread. -->
      <div v-if="currentSection" class="th-tables">
        <div v-for="table in currentSection.tables" :key="table.key" class="th-table">
          <ToolReferenceTable
            :table-key="table.key"
            :title="table.title"
            :unit="table.unit"
            :row-header="table.rowHeader"
            :columns="table.columns"
            :rows="table.rows"
            :active-row="table.activeRow"
            :active-column="table.activeColumn"
            scroll-to-active
          >
            <template #sketch>
              <ThreadProfileSketch v-if="table.sketch === 'profile'" />
              <TighteningSketch v-else-if="table.sketch === 'tightening'" />
              <HoleSketch v-else :variant="table.sketch" />
            </template>
          </ToolReferenceTable>
          <small v-if="table.note" class="th-table-note">{{ table.note }}</small>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped lang="scss">
// Like the other tools: inputs and result cards stay in view, the reference
// tables below take the remaining height and scroll on their own. On a narrow
// screen everything stacks and the whole tab scrolls.
.th {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);

  > :not(.th-details) {
    flex-shrink: 0;
  }
}

.th-panel {
  padding: var(--space-3) var(--space-4);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.th-inputs {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--space-5);
}

.th-code {
  min-width: 10rem;
  line-height: 2.5rem;
  font-size: var(--font-size-xl);
  font-weight: 600;
  white-space: nowrap;
}

.th-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.th-label {
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--p-text-muted-color);
}

.th-thread-select {
  min-width: 10rem;
}

.th-results {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(20rem, 1fr));
  gap: var(--space-2);
}

.th-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-width: 0;
}

.th-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.th-card-title {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
}

.th-card-tag {
  margin-left: auto;
  font-weight: 600;
}

.th-card-empty {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.th-card-note {
  margin-top: auto;
  color: var(--p-text-muted-color);
}

.th-rows {
  margin: 0;
  display: flex;
  flex-direction: column;
}

.th-row {
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

.th-row-value {
  font-weight: 500;

  &--emphasis {
    font-weight: 700;
    color: var(--p-primary-color);
  }
}

.th-row-missing {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.th-details {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.th-section-switch {
  align-self: flex-start;
}

// The tables of a section stack, each scrolling inside its own card.
.th-tables {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.th-table {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.th-table-note {
  color: var(--p-text-muted-color);
}

@media (max-width: $bp-lg) {
  .th {
    height: auto;
  }

  .th-details {
    overflow-y: visible;
  }
}
</style>
