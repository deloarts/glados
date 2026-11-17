<script setup lang="ts">
/**
 * Inputs of a crushing point: the largest body part that can get in, with
 * its minimum gap, and optionally the gap as built.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { numberOptions } from '../utils/safetyDistance/format'
import { LIMITS } from '../utils/safetyDistance/inputs'
import { MINIMUM_GAPS } from '../utils/safetyDistance/iso13854'
import { BODY_PARTS } from '../utils/safetyDistance/types'
import type { CrushingInputs } from '../utils/safetyDistance/types'
import SafetyDistanceField from './SafetyDistanceField.vue'

const model = defineModel<CrushingInputs>({ required: true })

const { t } = useI18n()
const { formatNumber } = useLocaleFormat()

const F = 'tools.safetyDistance.fields'

function set<K extends keyof CrushingInputs>(key: K, value: CrushingInputs[K]) {
  model.value = { ...model.value, [key]: value }
}

const partOptions = computed(() =>
  BODY_PARTS.map((value) => ({
    value,
    label: `${t(`${F}.bodyPart.${value}`)} (${formatNumber(MINIMUM_GAPS[value], numberOptions(0))} mm)`,
  })),
)
</script>

<template>
  <div class="sd-crushing">
    <div class="sd-crushing-grid">
      <div class="sd-crushing-field">
        <label id="sd-cr-part-label" for="sd-cr-part" class="sd-crushing-label">{{ t(`${F}.bodyPart.label`) }}</label>
        <Select
          :model-value="model.bodyPart"
          :options="partOptions"
          option-label="label"
          option-value="value"
          :placeholder="t(`${F}.bodyPart.placeholder`)"
          input-id="sd-cr-part"
          aria-labelledby="sd-cr-part-label"
          data-testid="sd-cr-part"
          @update:model-value="set('bodyPart', $event ?? null)"
        />
        <small class="sd-crushing-hint">{{ t(`${F}.bodyPart.hint`) }}</small>
      </div>
      <SafetyDistanceField
        id="sd-cr-a"
        :model-value="model.gap"
        :label="t(`${F}.crushingGap.label`)"
        symbol="a"
        unit="mm"
        :hint="t(`${F}.crushingGap.hint`)"
        :max="LIMITS.length.max"
        @update:model-value="set('gap', $event)"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.sd-crushing-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(13rem, 1fr));
  gap: var(--space-3) var(--space-4);
  align-items: start;
}

.sd-crushing-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.sd-crushing-label {
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.sd-crushing-hint {
  color: var(--p-text-muted-color);
  line-height: 1.35;
}
</style>
