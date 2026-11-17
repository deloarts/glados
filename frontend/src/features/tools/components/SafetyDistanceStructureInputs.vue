<script setup lang="ts">
/**
 * Inputs for reaching over a protective structure such as a fence: the
 * height of the hazard and of the structure, optionally the distance as
 * built, and whether the lower values of the low risk table may be used.
 */
import { useI18n } from 'vue-i18n'

import { LIMITS } from '../utils/safetyDistance/inputs'
import type { StructureInputs } from '../utils/safetyDistance/types'
import SafetyDistanceField from './SafetyDistanceField.vue'

const model = defineModel<StructureInputs>({ required: true })

const { t } = useI18n()

const F = 'tools.safetyDistance.fields'

function set<K extends keyof StructureInputs>(key: K, value: StructureInputs[K]) {
  model.value = { ...model.value, [key]: value }
}
</script>

<template>
  <div class="sd-structure">
    <div class="sd-structure-grid">
      <SafetyDistanceField
        id="sd-st-hh"
        :model-value="model.hazardHeight"
        :label="t(`${F}.structureHazardHeight.label`)"
        symbol="h_h"
        unit="mm"
        :hint="t(`${F}.structureHazardHeight.hint`)"
        :max="LIMITS.length.max"
        @update:model-value="set('hazardHeight', $event)"
      />
      <SafetyDistanceField
        id="sd-st-hps"
        :model-value="model.structureHeight"
        :label="t(`${F}.structureHeight.label`)"
        symbol="h_ps"
        unit="mm"
        :hint="t(`${F}.structureHeight.hint`)"
        :max="LIMITS.length.max"
        @update:model-value="set('structureHeight', $event)"
      />
      <SafetyDistanceField
        id="sd-st-sh"
        :model-value="model.distance"
        :label="t(`${F}.structureDistance.label`)"
        symbol="s_h"
        unit="mm"
        :hint="t(`${F}.structureDistance.hint`)"
        :max="LIMITS.length.max"
        @update:model-value="set('distance', $event)"
      />
    </div>
    <div>
      <div class="sd-structure-toggle">
        <ToggleSwitch
          :model-value="model.lowRisk"
          input-id="sd-st-low"
          data-testid="sd-st-low"
          @update:model-value="set('lowRisk', $event)"
        />
        <label for="sd-st-low">{{ t(`${F}.lowRisk.label`) }}</label>
      </div>
      <small class="sd-structure-hint">{{ t(`${F}.lowRisk.hint`) }}</small>
    </div>
  </div>
</template>

<style scoped lang="scss">
.sd-structure {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.sd-structure-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(13rem, 1fr));
  gap: var(--space-3) var(--space-4);
  align-items: start;
}

.sd-structure-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.sd-structure-hint {
  display: block;
  margin-top: var(--space-1);
  color: var(--p-text-muted-color);
  line-height: 1.35;
}
</style>
