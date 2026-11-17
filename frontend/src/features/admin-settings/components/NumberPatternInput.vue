<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { hasPipeInCharacterClass, testNumberPattern } from '../utils/numberPatternTest'

/**
 * A number pattern field with its live tester: the admin types a sample and
 * sees at once whether the pattern accepts it. The sample is never saved.
 */
defineProps<{
  inputId: string
  disabled?: boolean
}>()

const pattern = defineModel<string>({ required: true })

const { t } = useI18n()

const sample = ref('')
const result = computed(() => testNumberPattern(pattern.value, sample.value))
</script>

<template>
  <div class="pattern-row">
    <InputText
      :id="inputId"
      v-model="pattern"
      :maxlength="200"
      :invalid="result === 'invalid'"
      :disabled="disabled"
    />
    <InputText
      v-model="sample"
      class="pattern-sample"
      :placeholder="t('adminSettings.numbering.patternSamplePlaceholder')"
      :disabled="disabled || !pattern"
    />
    <span :class="['pattern-result', `pattern-result--${result}`]">
      {{ t(`adminSettings.numbering.patternResult.${result}`) }}
    </span>
  </div>
  <Message v-if="hasPipeInCharacterClass(pattern)" severity="warn" :closable="false">
    {{ t('adminSettings.numbering.pipeInClassWarning') }}
  </Message>
</template>

<style scoped lang="scss">
.pattern-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.pattern-sample {
  max-width: 12rem;
  font-family: monospace;
}

.pattern-result {
  font-size: var(--font-size-sm);
  white-space: nowrap;
  color: var(--p-text-muted-color);

  &--match {
    color: var(--p-green-500);
  }

  &--mismatch,
  &--invalid {
    color: var(--p-red-500);
  }
}
</style>
