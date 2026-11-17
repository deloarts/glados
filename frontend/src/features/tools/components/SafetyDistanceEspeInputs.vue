<script setup lang="ts">
/**
 * Inputs of electro-sensitive protective equipment approached at a right
 * angle: a light curtain with its field and hazard heights, a multi-beam
 * device with its beam heights, or a single beam.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { LIMITS, MAX_BEAMS } from '../utils/safetyDistance/inputs'
import { ESPE_DEVICES } from '../utils/safetyDistance/types'
import type { EspeInputs } from '../utils/safetyDistance/types'
import SafetyDistanceField from './SafetyDistanceField.vue'
import SafetyDistanceNumberList from './SafetyDistanceNumberList.vue'
import SafetyDistanceText from './SafetyDistanceText.vue'

const model = defineModel<EspeInputs>({ required: true })

const { t } = useI18n()

const P = 'tools.safetyDistance'
const F = `${P}.fields`

function set<K extends keyof EspeInputs>(key: K, value: EspeInputs[K]) {
  model.value = { ...model.value, [key]: value }
}

const deviceOptions = computed(() => ESPE_DEVICES.map((value) => ({ value, label: t(`${P}.devices.${value}`) })))
const environmentOptions = computed(() => [
  { value: true, label: t(`${P}.environment.industrial`) },
  { value: false, label: t(`${P}.environment.public`) },
])
</script>

<template>
  <div class="sd-espe">
    <div class="sd-espe-choice">
      <span id="sd-device-label" class="sd-espe-label">{{ t(`${P}.deviceLabel`) }}</span>
      <SelectButton
        :model-value="model.device"
        :options="deviceOptions"
        option-label="label"
        option-value="value"
        :allow-empty="false"
        aria-labelledby="sd-device-label"
        data-testid="sd-device"
        @update:model-value="set('device', $event)"
      />
      <small class="sd-espe-hint">{{ t(`${P}.deviceHints.${model.device}`) }}</small>
    </div>

    <template v-if="model.device === 'curtain'">
      <div class="sd-espe-grid">
        <SafetyDistanceField
          id="sd-de"
          :model-value="model.detection"
          :label="t(`${F}.detection.label`)"
          symbol="d_e"
          unit="mm"
          :hint="t(`${F}.detection.hint`)"
          :min="LIMITS.detection.min"
          :max="LIMITS.detection.max"
          @update:model-value="set('detection', $event)"
        />
        <SafetyDistanceField
          id="sd-hh"
          :model-value="model.hazardHeight"
          :label="t(`${F}.hazardHeight.label`)"
          symbol="H_H"
          unit="mm"
          :hint="t(`${F}.hazardHeight.hint`)"
          :max="LIMITS.length.max"
          @update:model-value="set('hazardHeight', $event)"
        />
        <SafetyDistanceField
          id="sd-hdt"
          :model-value="model.topEdge"
          :label="t(`${F}.topEdge.label`)"
          symbol="H_DT"
          unit="mm"
          :hint="t(`${F}.topEdge.hint`)"
          :max="LIMITS.length.max"
          @update:model-value="set('topEdge', $event)"
        />
        <SafetyDistanceField
          id="sd-hdb"
          :model-value="model.bottomEdge"
          :label="t(`${F}.bottomEdge.label`)"
          symbol="H_DB"
          unit="mm"
          :hint="t(`${F}.bottomEdge.hint`)"
          :max="LIMITS.length.max"
          @update:model-value="set('bottomEdge', $event)"
        />
      </div>

      <div class="sd-espe-choice">
        <span id="sd-env-label" class="sd-espe-label">{{ t(`${P}.environment.label`) }}</span>
        <SelectButton
          :model-value="model.industrial"
          :options="environmentOptions"
          option-label="label"
          option-value="value"
          :allow-empty="false"
          aria-labelledby="sd-env-label"
          data-testid="sd-environment"
          @update:model-value="set('industrial', $event)"
        />
        <small class="sd-espe-hint">{{ t(`${P}.environment.hint`) }}</small>
      </div>

      <div class="sd-espe-toggle">
        <ToggleSwitch
          :model-value="model.restart"
          input-id="sd-restart"
          data-testid="sd-restart"
          @update:model-value="set('restart', $event)"
        />
        <label for="sd-restart">{{ t(`${F}.restart.label`) }}</label>
      </div>
      <small class="sd-espe-hint sd-espe-hint--toggle"><SafetyDistanceText :text="t(`${F}.restart.hint`)" /></small>

      <div class="sd-espe-toggle">
        <ToggleSwitch
          :model-value="model.structureAbove"
          input-id="sd-above"
          data-testid="sd-above"
          @update:model-value="set('structureAbove', $event)"
        />
        <label for="sd-above">{{ t(`${F}.structureAbove.label`) }}</label>
      </div>
      <div v-if="model.structureAbove" class="sd-espe-grid sd-espe-nested">
        <SafetyDistanceField
          id="sd-hgt"
          :model-value="model.structureTop"
          :label="t(`${F}.structureTop.label`)"
          symbol="H_GT"
          unit="mm"
          :hint="t(`${F}.structureTop.hint`)"
          :max="LIMITS.length.max"
          @update:model-value="set('structureTop', $event)"
        />
      </div>

      <div class="sd-espe-toggle">
        <ToggleSwitch
          :model-value="model.structureBelow"
          input-id="sd-below"
          data-testid="sd-below"
          @update:model-value="set('structureBelow', $event)"
        />
        <label for="sd-below">{{ t(`${F}.structureBelow.label`) }}</label>
      </div>
      <div v-if="model.structureBelow" class="sd-espe-grid sd-espe-nested">
        <SafetyDistanceField
          id="sd-hgb"
          :model-value="model.structureGap"
          :label="t(`${F}.structureGap.label`)"
          symbol="H_GB"
          unit="mm"
          :hint="t(`${F}.structureGap.hint`)"
          :max="LIMITS.length.max"
          @update:model-value="set('structureGap', $event)"
        />
      </div>
    </template>

    <template v-else-if="model.device === 'multiBeam'">
      <div class="sd-espe-grid">
        <SafetyDistanceNumberList
          id="sd-beams"
          :model-value="model.beamHeights"
          :label="t(`${F}.beamHeights.label`)"
          unit="mm"
          :hint="t(`${F}.beamHeights.hint`)"
          :min="LIMITS.length.min"
          :max="LIMITS.length.max"
          :max-count="MAX_BEAMS"
          @update:model-value="set('beamHeights', $event)"
        />
        <SafetyDistanceField
          id="sd-beam-hh"
          :model-value="model.hazardHeight"
          :label="t(`${F}.hazardHeight.label`)"
          symbol="H_H"
          unit="mm"
          :hint="t(`${F}.hazardHeight.beamsHint`)"
          :max="LIMITS.length.max"
          @update:model-value="set('hazardHeight', $event)"
        />
        <SafetyDistanceField
          v-if="!model.stepArrangement"
          id="sd-oh"
          :model-value="model.openingHeight"
          :label="t(`${F}.openingHeight.label`)"
          symbol="h"
          unit="mm"
          :hint="t(`${F}.openingHeight.hint`)"
          :max="LIMITS.length.max"
          @update:model-value="set('openingHeight', $event)"
        />
      </div>
      <div class="sd-espe-toggle">
        <ToggleSwitch
          :model-value="model.stepArrangement"
          input-id="sd-step"
          data-testid="sd-step"
          @update:model-value="set('stepArrangement', $event)"
        />
        <label for="sd-step">{{ t(`${F}.stepArrangement.label`) }}</label>
      </div>
      <small class="sd-espe-hint sd-espe-hint--toggle">{{ t(`${F}.stepArrangement.hint`) }}</small>
      <div v-if="model.stepArrangement" class="sd-espe-grid sd-espe-nested">
        <SafetyDistanceField
          id="sd-hs"
          :model-value="model.stepHeight"
          :label="t(`${F}.stepHeight.label`)"
          symbol="H_S"
          unit="mm"
          :hint="t(`${F}.stepHeight.hint`)"
          :max="LIMITS.length.max"
          @update:model-value="set('stepHeight', $event)"
        />
      </div>
      <div class="sd-espe-choice">
        <span id="sd-env-label" class="sd-espe-label">{{ t(`${P}.environment.label`) }}</span>
        <SelectButton
          :model-value="model.industrial"
          :options="environmentOptions"
          option-label="label"
          option-value="value"
          :allow-empty="false"
          aria-labelledby="sd-env-label"
          data-testid="sd-environment"
          @update:model-value="set('industrial', $event)"
        />
      </div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.sd-espe {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.sd-espe-choice {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-1);
}

.sd-espe-label {
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--p-text-muted-color);
}

.sd-espe-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(13rem, 1fr));
  gap: var(--space-3) var(--space-4);
  align-items: start;
}

.sd-espe-nested {
  padding-left: var(--space-4);
  border-left: 2px solid var(--p-content-border-color);
}

.sd-espe-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.sd-espe-hint {
  color: var(--p-text-muted-color);
  line-height: 1.35;
}

.sd-espe-hint--toggle {
  margin-top: -0.5rem;
}
</style>
