<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAppToast } from '@/core/composables/useAppToast'
import { publishToolState, useInitialToolInputs } from '../composables/useToolState'
import {
  calculateSafetyDistance,
  safetyDistanceSnapshot,
  usesResponseTime,
  usesSupplement,
} from '../utils/safetyDistance/calculate'
import { emptySafetyDistanceInputs, LIMITS } from '../utils/safetyDistance/inputs'
import { decodeSafetyDistanceInputs, encodeSafetyDistanceInputs } from '../utils/safetyDistance/inputRecord'
import { summarizeSafetyDistance } from '../utils/safetyDistance/summary'
import { HOLD_TO_RUN_ACTUATIONS, MODE_GROUPS, modeGroup } from '../utils/safetyDistance/types'
import type { ModeGroup, SafetyDistanceInputs, SafetyDistanceMode } from '../utils/safetyDistance/types'
import SafetyDistanceBeamSketch from './SafetyDistanceBeamSketch.vue'
import SafetyDistanceCrushingInputs from './SafetyDistanceCrushingInputs.vue'
import SafetyDistanceCrushingSketch from './SafetyDistanceCrushingSketch.vue'
import SafetyDistanceEspeInputs from './SafetyDistanceEspeInputs.vue'
import SafetyDistanceEspeSketch from './SafetyDistanceEspeSketch.vue'
import SafetyDistanceField from './SafetyDistanceField.vue'
import SafetyDistanceGuardInputs from './SafetyDistanceGuardInputs.vue'
import SafetyDistanceHingeSketch from './SafetyDistanceHingeSketch.vue'
import SafetyDistanceOpeningInputs from './SafetyDistanceOpeningInputs.vue'
import SafetyDistanceOpeningSketch from './SafetyDistanceOpeningSketch.vue'
import SafetyDistanceParallelInputs from './SafetyDistanceParallelInputs.vue'
import SafetyDistanceParallelSketch from './SafetyDistanceParallelSketch.vue'
import SafetyDistanceReachSketch from './SafetyDistanceReachSketch.vue'
import SafetyDistanceReference from './SafetyDistanceReference.vue'
import SafetyDistanceResponseTime from './SafetyDistanceResponseTime.vue'
import SafetyDistanceResult from './SafetyDistanceResult.vue'
import SafetyDistanceSteps from './SafetyDistanceSteps.vue'
import SafetyDistanceStructureInputs from './SafetyDistanceStructureInputs.vue'
import SafetyDistanceStructureSketch from './SafetyDistanceStructureSketch.vue'
import SafetyDistanceTwoHandInputs from './SafetyDistanceTwoHandInputs.vue'

const { t } = useI18n()
const toast = useAppToast()

const P = 'tools.safetyDistance'

// A saved calculation hands back the record the tab published. It is read
// like any untrusted input: an unreadable part is left empty and the user is
// told once. Without one the tab starts cleared.
function startInputs(): SafetyDistanceInputs {
  const saved = useInitialToolInputs()
  if (saved) {
    const decoded = decodeSafetyDistanceInputs(saved)
    if (decoded.invalid) toast.warn('', t('tools.calculations.errors.invalidInputs'))
    return decoded.inputs
  }
  return emptySafetyDistanceInputs()
}

const inputs = ref<SafetyDistanceInputs>(startInputs())
const result = computed(() => calculateSafetyDistance(inputs.value))

// The first switch picks the standard, the second the mode within it.
// Coming back to a group returns to the mode last used there.
const lastMode = reactive<Partial<Record<ModeGroup, SafetyDistanceMode>>>({})
watch(
  () => inputs.value.mode,
  (mode) => (lastMode[modeGroup(mode)] = mode),
  { immediate: true },
)
const group = computed<ModeGroup>({
  get: () => modeGroup(inputs.value.mode),
  set: (value) => (inputs.value.mode = lastMode[value] ?? MODE_GROUPS[value][0]),
})
const groupOptions = computed(() =>
  (Object.keys(MODE_GROUPS) as ModeGroup[]).map((value) => ({ value, label: t(`${P}.groups.${value}`) })),
)
const modeOptions = computed(() => MODE_GROUPS[group.value].map((value) => ({ value, label: t(`${P}.modes.${value}`) })))
const actuationOptions = computed(() =>
  HOLD_TO_RUN_ACTUATIONS.map((value) => ({ value, label: t(`${P}.fields.actuation.${value}`) })),
)

const modeLabel = computed(() => {
  const mode = inputs.value.mode
  return mode === 'espe' ? t(`${P}.devices.${inputs.value.espe.device}`) : t(`${P}.modes.${mode}`)
})

const inputsTitle = computed(() => t(`${P}.sections.inputs.${inputs.value.mode}`))
const showSupplement = computed(() => usesSupplement(inputs.value))
const showResponseTime = computed(() => usesResponseTime(inputs.value))

// ── Saving ───────────────────────────────────────────────────────────────────

// The record holds only the keys the current mode uses; it is what a saved
// calculation stores and hands back.
const encoded = computed(() => encodeSafetyDistanceInputs(inputs.value))
const snapshot = computed(() => safetyDistanceSnapshot(inputs.value, result.value))
const summary = computed(() => summarizeSafetyDistance(snapshot.value, t))

publishToolState(() => ({
  inputs: encoded.value,
  results: snapshot.value,
  title: summary.value,
  description: summary.value,
}))
</script>

<template>
  <div class="sd">
    <section class="sd-panel sd-head">
      <div class="sd-mode">
        <span id="sd-group-label" class="sd-label">{{ t(`${P}.groupLabel`) }}</span>
        <SelectButton
          v-model="group"
          :options="groupOptions"
          option-label="label"
          option-value="value"
          :allow-empty="false"
          aria-labelledby="sd-group-label"
          data-testid="sd-group"
        />
      </div>
      <div v-if="modeOptions.length > 1" class="sd-mode">
        <span id="sd-mode-label" class="sd-label">{{ t(`${P}.modeLabels.${group}`) }}</span>
        <SelectButton
          v-model="inputs.mode"
          :options="modeOptions"
          option-label="label"
          option-value="value"
          :allow-empty="false"
          aria-labelledby="sd-mode-label"
          data-testid="sd-mode"
        />
      </div>
      <p class="sd-mode-description">{{ t(`${P}.modeDescriptions.${inputs.mode}`) }}</p>
    </section>

    <div class="sd-body">
      <div class="sd-column">
        <section class="sd-panel" data-testid="sd-device-inputs">
          <h3 class="sd-section-title">{{ inputsTitle }}</h3>
          <SafetyDistanceEspeInputs v-if="inputs.mode === 'espe'" v-model="inputs.espe" />
          <SafetyDistanceParallelInputs v-else-if="inputs.mode === 'parallel'" v-model="inputs.parallel" />
          <SafetyDistanceGuardInputs v-else-if="inputs.mode === 'guard'" v-model="inputs.guard" />
          <SafetyDistanceTwoHandInputs v-else-if="inputs.mode === 'twoHand'" v-model="inputs.twoHand" />
          <SafetyDistanceStructureInputs v-else-if="inputs.mode === 'structure'" v-model="inputs.structure" />
          <SafetyDistanceOpeningInputs v-else-if="inputs.mode === 'opening'" v-model="inputs.opening" />
          <SafetyDistanceCrushingInputs v-else-if="inputs.mode === 'crushing'" v-model="inputs.crushing" />
          <div v-else class="sd-choice">
            <span id="sd-actuation-label" class="sd-label">{{ t(`${P}.fields.actuation.label`) }}</span>
            <SelectButton
              v-model="inputs.holdToRun.actuation"
              :options="actuationOptions"
              option-label="label"
              option-value="value"
              :allow-empty="false"
              aria-labelledby="sd-actuation-label"
              data-testid="sd-actuation"
            />
          </div>
          <div v-if="showSupplement" class="sd-supplement">
            <SafetyDistanceField
              id="sd-z"
              v-model="inputs.supplement"
              :label="t(`${P}.fields.supplement.label`)"
              symbol="Z"
              unit="mm"
              :hint="t(`${P}.fields.supplement.hint`)"
              :max="LIMITS.length.max"
            />
          </div>
        </section>

        <section v-if="showResponseTime" class="sd-panel" data-testid="sd-response-time">
          <h3 class="sd-section-title">{{ t(`${P}.sections.responseTime`) }}</h3>
          <SafetyDistanceResponseTime v-model="inputs.responseTime" :result="result.responseTime" />
        </section>
      </div>

      <div class="sd-column">
        <SafetyDistanceResult class="sd-panel" :result="result" :label="modeLabel" />
        <section class="sd-panel sd-sketches" data-testid="sd-sketches">
          <template v-if="inputs.mode === 'espe'">
            <SafetyDistanceEspeSketch v-if="inputs.espe.device === 'curtain'" :inputs="inputs.espe" :result="result" />
            <SafetyDistanceBeamSketch v-else :inputs="inputs.espe" />
          </template>
          <SafetyDistanceParallelSketch v-else-if="inputs.mode === 'parallel'" :inputs="inputs.parallel" :result="result" />
          <SafetyDistanceStructureSketch v-else-if="inputs.mode === 'structure'" :inputs="inputs.structure" :result="result" />
          <SafetyDistanceOpeningSketch v-else-if="inputs.mode === 'opening'" :inputs="inputs.opening" :result="result" />
          <SafetyDistanceCrushingSketch v-else-if="inputs.mode === 'crushing'" :inputs="inputs.crushing" :result="result" />
          <template v-else>
            <SafetyDistanceHingeSketch
              v-if="inputs.mode === 'guard' && inputs.guard.openingMethod === 'hinged'"
              :inputs="inputs.guard"
              :result="result"
            />
            <SafetyDistanceReachSketch :inputs="inputs" :result="result" />
          </template>
        </section>
        <SafetyDistanceSteps class="sd-panel" :result="result" />
      </div>
    </div>

    <SafetyDistanceReference :inputs="inputs" />
  </div>
</template>

<style scoped lang="scss">
// Inputs on the left, result and worked calculation on the right; the
// reference tables run across the full width below. On a narrow screen
// everything stacks, and the tab scrolls as one page.
.sd {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.sd-panel {
  padding: var(--space-3) var(--space-4);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.sd-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--space-3) var(--space-5);
}

.sd-mode,
.sd-choice {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-1);
}

.sd-label {
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--p-text-muted-color);
}

.sd-mode-description {
  flex: 1 1 100%;
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.sd-body {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(28rem, 1fr));
  gap: var(--space-2);
  align-items: start;
}

.sd-column {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
}

.sd-sketches {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.sd-section-title {
  margin: 0 0 var(--space-3);
  font-size: var(--font-size-md);
  font-weight: 600;
}

.sd-supplement {
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--p-content-border-color);
  max-width: 24rem;
}

@media (max-width: $bp-sm) {
  .sd-body {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
