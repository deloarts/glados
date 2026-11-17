<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useFitFormat } from '../composables/useFitFormat'
import type { Fit, FitFigureKind, FitType } from '../utils/iso286/fit'
import type { FitPart, LimitResult } from '../utils/iso286/toleranceClass'
import FitPartSketch from './FitPartSketch.vue'
import FitTypeSketch from './FitTypeSketch.vue'

// The limits section (hole and shaft) and the fit types section render as two
// separate blocks so the calculator can place them independently, the limits
// next to the tolerance zone diagram on a wide screen.
const props = defineProps<{
  section: 'limits' | 'fitTypes'
  size: number | null
  hole: LimitResult
  shaft: LimitResult
  fit: Fit | null
}>()

const { t } = useI18n()
const fmt = useFitFormat()

interface Formula {
  key: string
  text: string
  /** The formula worked through with the current values, when there are any. */
  worked: string | null
}

// "a − b" with the subtrahend in parentheses when it is negative, so the
// written-out calculation reads like it would on paper.
function minus(a: string, b: number, bText: string): string {
  return `${a} − ${b < 0 ? `(${bText})` : bText}`
}

function plus(size: number, deviation: number): string {
  const sign = deviation < 0 ? '−' : '+'
  return `${fmt.nominal(size)} mm ${sign} ${fmt.amountMm(Math.abs(deviation))}`
}

function partFormulas(part: FitPart, result: LimitResult): Formula[] {
  const n = props.size
  const values = result.ok && n !== null ? { n, upper: result.upper, lower: result.lower } : null
  return [
    {
      key: 'max',
      text: t(`tools.fitCalculator.explain.formulas.${part}Max`),
      worked: values
        ? `= ${plus(values.n, values.upper)} = ${fmt.limitSize(values.n, values.upper)}`
        : null,
    },
    {
      key: 'min',
      text: t(`tools.fitCalculator.explain.formulas.${part}Min`),
      worked: values
        ? `= ${plus(values.n, values.lower)} = ${fmt.limitSize(values.n, values.lower)}`
        : null,
    },
    {
      key: 'tolerance',
      text: t(`tools.fitCalculator.explain.formulas.${part}Tolerance`),
      worked: values
        ? `= ${minus(fmt.deviationMm(values.upper), values.lower, fmt.deviationMm(values.lower))} = ${fmt.amountMm(values.upper - values.lower)}`
        : null,
    },
  ]
}

const parts = computed(() =>
  (['hole', 'shaft'] as const).map((part) => ({
    part,
    formulas: partFormulas(part, part === 'hole' ? props.hole : props.shaft),
  })),
)

const FIGURES: Record<FitType, [FitFigureKind, FitFigureKind]> = {
  clearance: ['maxClearance', 'minClearance'],
  transition: ['maxClearance', 'maxInterference'],
  interference: ['maxInterference', 'minInterference'],
}

// Which limit size of which part each figure subtracts, in µm deviations.
function figureOperands(kind: FitFigureKind, hole: { upper: number; lower: number }, shaft: { upper: number; lower: number }) {
  switch (kind) {
    case 'maxClearance':
      return [hole.upper, shaft.lower] as const
    case 'minClearance':
      return [hole.lower, shaft.upper] as const
    case 'maxInterference':
      return [shaft.upper, hole.lower] as const
    case 'minInterference':
      return [shaft.lower, hole.upper] as const
  }
}

function workedFigure(kind: FitFigureKind): string | null {
  const h = props.hole
  const s = props.shaft
  const n = props.size
  if (!h.ok || !s.ok || n === null) return null
  const [a, b] = figureOperands(kind, h, s)
  return `= ${fmt.limitSize(n, a)} − ${fmt.limitSize(n, b)} = ${fmt.amountMm(a - b)}`
}

const fitTypes = computed(() =>
  (['clearance', 'transition', 'interference'] as const).map((type) => {
    const active = props.fit?.type === type
    return {
      type,
      active,
      figures: FIGURES[type].map((kind, index) => ({
        kind,
        number: index + 1,
        text: t(`tools.fitCalculator.explain.formulas.${kind}`),
        worked: active ? workedFigure(kind) : null,
      })),
    }
  }),
)
</script>

<template>
  <section v-if="section === 'limits'" class="explain" data-testid="fit-explanation-limits">
    <h3 class="explain-title">{{ t('tools.fitCalculator.explain.title') }}</h3>

    <div class="explain-grid explain-grid--parts">
      <div v-for="p in parts" :key="p.part" class="explain-item">
        <h4 class="explain-subtitle">{{ t(`tools.fitCalculator.${p.part}`) }}</h4>
        <FitPartSketch :part="p.part" />
        <ul class="explain-formulas">
          <li v-for="f in p.formulas" :key="f.key">
            <span class="explain-formula">{{ f.text }}</span>
            <span v-if="f.worked" class="explain-worked" :data-testid="`fit-explain-${p.part}-${f.key}`">{{ f.worked }}</span>
          </li>
        </ul>
      </div>
    </div>
  </section>

  <section v-else class="explain" data-testid="fit-explanation-types">
    <h3 class="explain-title">{{ t('tools.fitCalculator.explain.fitTypesTitle') }}</h3>
    <div class="explain-grid explain-grid--types">
      <div
        v-for="ft in fitTypes"
        :key="ft.type"
        class="explain-item explain-item--type"
        :class="{ 'explain-item--active': ft.active }"
        :data-testid="`fit-explain-type-${ft.type}`"
      >
        <div class="explain-type-header">
          <h4 class="explain-subtitle">{{ t(`tools.fitCalculator.types.${ft.type}`) }}</h4>
          <Tag v-if="ft.active" :value="t('tools.fitCalculator.explain.currentFit')" severity="secondary" />
        </div>
        <FitTypeSketch :type="ft.type" />
        <ul class="explain-formulas">
          <li v-for="f in ft.figures" :key="f.kind" class="explain-figure">
            <span class="explain-badge" aria-hidden="true">{{ f.number }}</span>
            <span class="explain-figure-body">
              <span class="explain-formula">{{ f.text }}</span>
              <span v-if="f.worked" class="explain-worked" :data-testid="`fit-explain-${f.kind}`">{{ f.worked }}</span>
            </span>
          </li>
        </ul>
      </div>
    </div>
  </section>
</template>

<style scoped lang="scss">
.explain {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-width: 0;
}

.explain-title {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
}

.explain-grid {
  // Fills the section, so when the row is taller than the content the
  // boxes stretch with it and stay level with their neighbours.
  flex: 1;
  display: grid;
  gap: var(--space-2);

  &--parts {
    grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
  }

  &--types {
    grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
  }
}

.explain-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);

  &--active {
    border-color: var(--p-primary-color);
    background: var(--p-highlight-bg);
  }
}

// Tall enough for the "current fit" tag, so the sketches of all three types
// start at the same height whether or not a header carries the tag.
.explain-type-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  min-height: 1.75rem;
}

.explain-subtitle {
  margin: 0;
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.explain-formulas {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  font-size: var(--font-size-sm);

  li {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  li.explain-figure {
    flex-direction: row;
    align-items: flex-start;
    gap: var(--space-2);
  }
}

.explain-figure-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.explain-badge {
  flex-shrink: 0;
  width: 1.15rem;
  height: 1.15rem;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--p-content-background);
  background: var(--p-text-color);
}

.explain-formula {
  font-weight: 500;
}

.explain-worked {
  color: var(--p-text-muted-color);
  font-variant-numeric: tabular-nums;
}
</style>
