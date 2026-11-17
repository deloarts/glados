<script setup lang="ts">
/** Inputs of a detection zone approached in parallel, such as a safety mat or a horizontal light curtain. */
import { useI18n } from 'vue-i18n'

import { LIMITS } from '../utils/safetyDistance/inputs'
import type { ParallelInputs } from '../utils/safetyDistance/types'
import SafetyDistanceField from './SafetyDistanceField.vue'

const model = defineModel<ParallelInputs>({ required: true })

const { t } = useI18n()

const F = 'tools.safetyDistance.fields'

function set<K extends keyof ParallelInputs>(key: K, value: ParallelInputs[K]) {
  model.value = { ...model.value, [key]: value }
}
</script>

<template>
  <div class="sd-parallel">
    <div class="sd-parallel-grid">
      <SafetyDistanceField
        id="sd-de"
        :model-value="model.detection"
        :label="t(`${F}.detection.label`)"
        symbol="d_e"
        unit="mm"
        :hint="t(`${F}.parallelDetection.hint`)"
        :min="LIMITS.parallelDetection.min"
        :max="LIMITS.parallelDetection.max"
        @update:model-value="set('detection', $event)"
      />
      <SafetyDistanceField
        id="sd-hd"
        :model-value="model.fieldHeight"
        :label="t(`${F}.fieldHeight.label`)"
        symbol="H_D"
        unit="mm"
        :hint="t(`${F}.fieldHeight.hint`)"
        :max="LIMITS.length.max"
        @update:model-value="set('fieldHeight', $event)"
      />
      <SafetyDistanceField
        id="sd-fd"
        :model-value="model.fieldDepth"
        :label="t(`${F}.fieldDepth.label`)"
        symbol="F_D"
        unit="mm"
        :hint="t(`${F}.fieldDepth.hint`)"
        :max="LIMITS.length.max"
        @update:model-value="set('fieldDepth', $event)"
      />
      <SafetyDistanceField
        id="sd-gd"
        :model-value="model.obstacleGap"
        :label="t(`${F}.obstacleGap.label`)"
        symbol="G_D"
        unit="mm"
        :hint="t(`${F}.obstacleGap.hint`)"
        :max="LIMITS.length.max"
        @update:model-value="set('obstacleGap', $event)"
      />
    </div>
    <div class="sd-parallel-toggle">
      <ToggleSwitch
        :model-value="model.standingDetected"
        input-id="sd-stand"
        data-testid="sd-stand"
        @update:model-value="set('standingDetected', $event)"
      />
      <label for="sd-stand">{{ t(`${F}.standingDetected.label`) }}</label>
    </div>
  </div>
</template>

<style scoped lang="scss">
.sd-parallel {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.sd-parallel-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(13rem, 1fr));
  gap: var(--space-3) var(--space-4);
  align-items: start;
}

.sd-parallel-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: 600;
}
</style>
