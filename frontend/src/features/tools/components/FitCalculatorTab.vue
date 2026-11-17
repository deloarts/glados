<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAppToast } from '@/core/composables/useAppToast'
import { localeTag } from '@/core/utils/dates'
import { useFitFormat } from '../composables/useFitFormat'
import { publishToolState, useInitialToolInputs } from '../composables/useToolState'
import { parseSavedSize, savedString } from '../utils/savedInputs'
import { calculateFit } from '../utils/iso286/fit'
import {
  availableGrades,
  classCode,
  closestGrade,
  limitDeviations,
  parseClass,
} from '../utils/iso286/toleranceClass'
import type { FitPart, LimitResult, ToleranceClass } from '../utils/iso286/toleranceClass'
import { MAX_SIZE } from '../utils/iso286/sizeRanges'
import { findRecommendation } from '../utils/fitRecommendations'
import type { FitRecommendation } from '../utils/fitRecommendations'
import FitClassPicker from './FitClassPicker.vue'
import FitExplanation from './FitExplanation.vue'
import FitPartCard from './FitPartCard.vue'
import FitRecommendations from './FitRecommendations.vue'
import FitResultCard from './FitResultCard.vue'
import ToleranceZoneDiagram from './ToleranceZoneDiagram.vue'

const DEFAULT_SIZE = 25
const DEFAULT_HOLE: ToleranceClass = { part: 'hole', letter: 'H', grade: 7 }
const DEFAULT_SHAFT: ToleranceClass = { part: 'shaft', letter: 'g', grade: 6 }

const { t } = useI18n()
const toast = useAppToast()
const fmt = useFitFormat()

/**
 * Reads the inputs of a saved calculation. Each part that is missing falls
 * back to its default silently; a part that is present but invalid also falls
 * back, and the user is told once.
 */
function readInputs(saved: Record<string, string> | null) {
  let invalid = false
  const rawSize = savedString(saved?.d)
  const rawHole = savedString(saved?.hole)
  const rawShaft = savedString(saved?.shaft)

  const savedSize = parseSavedSize(rawSize, DEFAULT_SIZE, MAX_SIZE)
  const size = savedSize.size
  if (savedSize.invalid) invalid = true

  const pick = (raw: string | null, part: FitPart, fallback: ToleranceClass) => {
    if (raw === null) return fallback
    const parsed = parseClass(raw)
    if (parsed && parsed.part === part) return parsed
    invalid = true
    return fallback
  }

  return {
    size,
    hole: pick(rawHole, 'hole', DEFAULT_HOLE),
    shaft: pick(rawShaft, 'shaft', DEFAULT_SHAFT),
    invalid,
  }
}

const initial = readInputs(useInitialToolInputs())
if (initial.invalid) toast.warn('', t('tools.calculations.errors.invalidInputs'))

const size = ref<number | null>(initial.size)
const holeLetter = ref(initial.hole.letter)
const holeGrade = ref(initial.hole.grade)
const shaftLetter = ref(initial.shaft.letter)
const shaftGrade = ref(initial.shaft.grade)

// A new letter keeps the grade when it exists for that letter, otherwise the
// nearest one, so picking "j" after "g6" lands on j6 instead of an empty card.
function keepGradeValid(part: FitPart, letter: string, grade: typeof holeGrade) {
  const next = closestGrade(availableGrades(part, letter, size.value ?? 0), grade.value)
  if (next !== null) grade.value = next
}
watch(holeLetter, (letter) => keepGradeValid('hole', letter, holeGrade))
watch(shaftLetter, (letter) => keepGradeValid('shaft', letter, shaftGrade))

const holeClass = computed<ToleranceClass>(() => ({
  part: 'hole',
  letter: holeLetter.value,
  grade: holeGrade.value,
}))
const shaftClass = computed<ToleranceClass>(() => ({
  part: 'shaft',
  letter: shaftLetter.value,
  grade: shaftGrade.value,
}))
const holeCode = computed(() => classCode(holeClass.value))
const shaftCode = computed(() => classCode(shaftClass.value))

const holeResult = computed<LimitResult>(() =>
  limitDeviations(size.value ?? Number.NaN, holeClass.value),
)
const shaftResult = computed<LimitResult>(() =>
  limitDeviations(size.value ?? Number.NaN, shaftClass.value),
)

const fit = computed(() => {
  const h = holeResult.value
  const s = shaftResult.value
  return h.ok && s.ok ? calculateFit(h, s) : null
})

const recommendation = computed(() => findRecommendation(holeCode.value, shaftCode.value))

function applyRecommendation(rec: FitRecommendation) {
  const hole = parseClass(rec.hole)
  const shaft = parseClass(rec.shaft)
  if (!hole || !shaft) return
  holeLetter.value = hole.letter
  holeGrade.value = hole.grade
  shaftLetter.value = shaft.letter
  shaftGrade.value = shaft.grade
}

const inputs = computed(() => ({
  d: size.value === null ? '' : String(size.value),
  hole: holeCode.value,
  shaft: shaftCode.value,
}))

// Limits in µm, as calculated; the saved snapshot must not depend on the
// viewer's number format.
function partSnapshot(code: string, result: LimitResult) {
  return result.ok
    ? { code, upper: result.upper, lower: result.lower }
    : { code, unavailable: result.reason }
}

publishToolState(() => ({
  inputs: inputs.value,
  results: {
    size: size.value,
    hole: partSnapshot(holeCode.value, holeResult.value),
    shaft: partSnapshot(shaftCode.value, shaftResult.value),
    fit: fit.value,
    recommendedSeries: recommendation.value?.series ?? null,
  },
  title: `Ø${size.value === null ? '' : fmt.nominal(size.value)} ${holeCode.value}/${shaftCode.value}`,
}))
</script>

<template>
  <div class="fit-calculator">
    <div class="fit-main">
      <section class="fit-panel fit-inputs">
        <span class="fit-code" data-testid="fit-code">
          <template v-if="size !== null">Ø{{ fmt.nominal(size) }} </template>
          <span class="fit-code-hole">{{ holeCode }}</span>/<span class="fit-code-shaft">{{ shaftCode }}</span>
        </span>
        <div class="fit-size">
          <label for="fit-size" class="fit-size-label">{{ t('tools.fitCalculator.nominalSize') }}</label>
          <InputNumber
            v-model="size"
            input-id="fit-size"
            :min="0"
            :max="MAX_SIZE"
            :min-fraction-digits="0"
            :max-fraction-digits="3"
            :locale="localeTag()"
            suffix=" mm"
            data-testid="fit-size"
            class="fit-size-input"
          />
        </div>
        <FitClassPicker v-model:letter="holeLetter" v-model:grade="holeGrade" part="hole" :size="size" />
        <FitClassPicker v-model:letter="shaftLetter" v-model:grade="shaftGrade" part="shaft" :size="size" />
      </section>

      <div class="fit-results">
        <FitPartCard part="hole" :code="holeCode" :size="size" :result="holeResult" />
        <FitPartCard part="shaft" :code="shaftCode" :size="size" :result="shaftResult" />
        <FitResultCard :fit="fit" :recommendation="recommendation" :size="size" />
      </div>

      <section class="fit-panel fit-details" data-testid="fit-details">
        <div class="fit-details-top">
          <ToleranceZoneDiagram
            v-if="holeResult.ok && shaftResult.ok"
            :hole-code="holeCode"
            :shaft-code="shaftCode"
            :hole="holeResult"
            :shaft="shaftResult"
          />
          <FitExplanation
            section="limits"
            class="fit-details-limits"
            :size="size"
            :hole="holeResult"
            :shaft="shaftResult"
            :fit="fit"
          />
        </div>
        <FitExplanation section="fitTypes" :size="size" :hole="holeResult" :shaft="shaftResult" :fit="fit" />
        <p class="fit-footnote">{{ t('tools.fitCalculator.footnote') }}</p>
      </section>
    </div>

    <FitRecommendations
      class="fit-aside"
      :hole-code="holeCode"
      :shaft-code="shaftCode"
      @select="applyRecommendation"
    />
  </div>
</template>

<style scoped lang="scss">
// Side by side, the calculator fills the tab: the inputs and result cards stay
// in view, the details card below them takes the remaining height and scrolls
// on its own, and the recommendations run the full height with their own
// scrolling list. On a narrow screen everything stacks and the whole tab
// scrolls as one page.
.fit-calculator {
  height: 100%;
  display: flex;
  gap: var(--space-2);
}

.fit-main {
  flex: 1 1 40rem;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);

  > :not(.fit-details) {
    flex-shrink: 0;
  }
}

.fit-details {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.fit-details-top {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--space-4);
}

// On a wide screen the tolerance zones take one third and the hole and shaft
// sketches the other two, side by side. Without a diagram (no standard values)
// the sketches keep the full width.
@media (min-width: $bp-2xl) {
  .fit-details-top {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .fit-details-limits {
    grid-column: span 2;
  }

  .fit-details-limits:only-child {
    grid-column: 1 / -1;
  }
}

.fit-aside {
  flex: 0 0 28rem;
  min-height: 0;
}

@media (max-width: $bp-lg) {
  .fit-calculator {
    height: auto;
    flex-wrap: wrap;
  }

  .fit-details {
    overflow-y: visible;
  }

  .fit-aside {
    flex: 1 1 100%;
  }
}

.fit-panel {
  padding: var(--space-3) var(--space-4);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.fit-inputs {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--space-5);
}

.fit-size {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.fit-size-label {
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--p-text-muted-color);
}

.fit-size-input :deep(input) {
  width: 8rem;
}

// Sits at the left of the input row, sized and aligned like an input so its
// baseline matches the fields next to it.
.fit-code {
  min-width: 10rem;
  line-height: 2.5rem;
  font-size: var(--font-size-xl);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.fit-code-hole {
  color: var(--p-blue-500);
}

.fit-code-shaft {
  color: var(--p-orange-500);
}

.fit-results {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
  gap: var(--space-2);
}

.fit-footnote {
  margin: 0;
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}
</style>
