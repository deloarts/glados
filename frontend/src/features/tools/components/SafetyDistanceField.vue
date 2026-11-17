<script setup lang="ts">
/** A labelled number input of the safety distance tool, with its symbol, unit and an optional hint. */
import { localeTag } from '@/core/utils/dates'
import SafetyDistanceText from './SafetyDistanceText.vue'

withDefaults(
  defineProps<{
    id: string
    label: string
    symbol?: string
    unit: string
    hint?: string
    min?: number
    max?: number
    digits?: number
  }>(),
  { symbol: '', hint: '', min: 0, max: 10000, digits: 1 },
)

const model = defineModel<number | null>({ required: true })
</script>

<template>
  <div class="sd-field">
    <label :for="id" class="sd-field-label">
      {{ label }}
      <SafetyDistanceText v-if="symbol" :text="symbol" class="sd-field-symbol" />
    </label>
    <InputNumber
      v-model="model"
      :input-id="id"
      :min="min"
      :max="max"
      :min-fraction-digits="0"
      :max-fraction-digits="digits"
      :use-grouping="false"
      :locale="localeTag()"
      :suffix="` ${unit}`"
      :data-testid="id"
      class="sd-field-input"
    />
    <small v-if="hint" class="sd-field-hint"><SafetyDistanceText :text="hint" /></small>
  </div>
</template>

<style scoped lang="scss">
.sd-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.sd-field-label {
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.sd-field-symbol {
  margin-left: var(--space-1);
  font-weight: 400;
  font-style: italic;
  color: var(--p-text-muted-color);
}

.sd-field-input {
  width: 100%;

  :deep(input) {
    width: 100%;
  }
}

.sd-field-hint {
  color: var(--p-text-muted-color);
  line-height: 1.35;
}
</style>
