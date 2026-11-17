<script setup lang="ts">
/**
 * Inputs of a two-hand control device: whether reaching in while operating
 * is prevented, which sets the reach of ISO 13855, and the type and actuator
 * spacing that ISO 13851 asks of the device itself.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { LIMITS } from '../utils/safetyDistance/inputs'
import { TWO_HAND_TYPES } from '../utils/safetyDistance/types'
import type { TwoHandInputs } from '../utils/safetyDistance/types'
import SafetyDistanceField from './SafetyDistanceField.vue'

const model = defineModel<TwoHandInputs>({ required: true })

const { t } = useI18n()

const F = 'tools.safetyDistance.fields'

function set<K extends keyof TwoHandInputs>(key: K, value: TwoHandInputs[K]) {
  model.value = { ...model.value, [key]: value }
}

const typeOptions = computed(() => TWO_HAND_TYPES.map((value) => ({ value, label: t(`${F}.twoHandType.${value}`) })))
</script>

<template>
  <div class="sd-two-hand">
    <div>
      <div class="sd-two-hand-toggle">
        <ToggleSwitch
          :model-value="model.encroachmentPrevented"
          input-id="sd-prevent"
          data-testid="sd-prevent"
          @update:model-value="set('encroachmentPrevented', $event)"
        />
        <label for="sd-prevent">{{ t(`${F}.encroachmentPrevented.label`) }}</label>
      </div>
      <small class="sd-two-hand-hint">{{ t(`${F}.encroachmentPrevented.hint`) }}</small>
    </div>

    <div class="sd-two-hand-grid">
      <div class="sd-two-hand-field">
        <label id="sd-two-hand-type-label" for="sd-two-hand-type" class="sd-two-hand-label">{{ t(`${F}.twoHandType.label`) }}</label>
        <Select
          :model-value="model.type"
          :options="typeOptions"
          option-label="label"
          option-value="value"
          :placeholder="t(`${F}.twoHandType.placeholder`)"
          show-clear
          input-id="sd-two-hand-type"
          aria-labelledby="sd-two-hand-type-label"
          data-testid="sd-two-hand-type"
          @update:model-value="set('type', $event ?? null)"
        />
        <small class="sd-two-hand-hint">{{ t(`${F}.twoHandType.hint`) }}</small>
      </div>
      <SafetyDistanceField
        id="sd-actuator-gap"
        :model-value="model.actuatorGap"
        :label="t(`${F}.actuatorGap.label`)"
        unit="mm"
        :hint="t(`${F}.actuatorGap.hint`)"
        :max="LIMITS.length.max"
        @update:model-value="set('actuatorGap', $event)"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.sd-two-hand {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.sd-two-hand-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(13rem, 1fr));
  gap: var(--space-3) var(--space-4);
  align-items: start;
}

.sd-two-hand-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.sd-two-hand-label {
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.sd-two-hand-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.sd-two-hand-hint {
  display: block;
  margin-top: var(--space-1);
  color: var(--p-text-muted-color);
  line-height: 1.35;
}

.sd-two-hand-field .sd-two-hand-hint {
  margin-top: 0;
}
</style>
