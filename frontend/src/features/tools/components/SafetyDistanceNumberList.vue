<script setup lang="ts">
/**
 * A list of numbers typed or pasted as text, such as stopping time
 * measurements or beam heights. The text stays as typed; the model receives
 * the values that could be read and lie within the limits, and the field
 * names everything else.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { localeTag } from '@/core/utils/dates'
import { parseNumberList } from '../utils/safetyDistance/inputs'
import SafetyDistanceText from './SafetyDistanceText.vue'

const props = withDefaults(
  defineProps<{
    id: string
    label: string
    unit: string
    hint?: string
    min: number
    max: number
    maxCount: number
    multiline?: boolean
  }>(),
  { hint: '', multiline: false },
)

const model = defineModel<number[]>({ required: true })

const { t } = useI18n()
const { formatNumber } = useLocaleFormat()

const decimalComma = computed(() => localeTag() === 'de-AT')

function format(values: readonly number[]): string {
  const separator = decimalComma.value ? '; ' : ', '
  return values.map((v) => formatNumber(v, { maximumFractionDigits: 6, useGrouping: false })).join(separator)
}

function read(text: string): { values: number[]; rejected: string[] } {
  const parsed = parseNumberList(text, decimalComma.value)
  const values: number[] = []
  const rejected = [...parsed.rejected]
  for (const value of parsed.values) {
    if (value >= props.min && value <= props.max && values.length < props.maxCount) values.push(value)
    else rejected.push(formatNumber(value, { maximumFractionDigits: 6, useGrouping: false }))
  }
  return { values, rejected }
}

const text = ref(format(model.value))
const rejected = ref<string[]>([])

function onInput(value: string | undefined) {
  text.value = value ?? ''
  const parsed = read(text.value)
  rejected.value = parsed.rejected
  model.value = parsed.values
}

// A model changed from outside (a reopened calculation) replaces the text;
// the user's own typing is left alone.
watch(model, (next) => {
  const current = read(text.value).values
  if (current.length !== next.length || current.some((v, i) => v !== next[i])) {
    text.value = format(next)
    rejected.value = []
  }
})
</script>

<template>
  <div class="sd-list">
    <label :for="id" class="sd-list-label">{{ label }} <span class="sd-list-unit">({{ unit }})</span></label>
    <Textarea
      v-if="multiline"
      :id="id"
      :model-value="text"
      rows="4"
      auto-resize
      class="sd-list-input"
      :data-testid="id"
      @update:model-value="onInput"
    />
    <InputText
      v-else
      :id="id"
      :model-value="text"
      class="sd-list-input"
      :data-testid="id"
      @update:model-value="onInput"
    />
    <small v-if="rejected.length > 0" class="sd-list-rejected" :data-testid="`${id}-rejected`">
      {{ t('tools.safetyDistance.list.rejected', { values: rejected.join(' ') }) }}
    </small>
    <small v-if="multiline" class="sd-list-count">{{ t('tools.safetyDistance.list.count', { n: model.length }) }}</small>
    <small v-if="hint" class="sd-list-hint"><SafetyDistanceText :text="hint" /></small>
  </div>
</template>

<style scoped lang="scss">
.sd-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.sd-list-label {
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.sd-list-unit {
  font-weight: 400;
  color: var(--p-text-muted-color);
}

.sd-list-input {
  width: 100%;
  font-variant-numeric: tabular-nums;
}

.sd-list-rejected {
  color: var(--p-red-500);
}

.sd-list-count,
.sd-list-hint {
  color: var(--p-text-muted-color);
  line-height: 1.35;
}
</style>
