<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import {
  ALL_GRADES,
  availableGrades,
  HOLE_LETTERS,
  SHAFT_LETTERS,
} from '../utils/iso286/toleranceClass'
import type { FitPart } from '../utils/iso286/toleranceClass'

const props = defineProps<{
  part: FitPart
  size: number | null
}>()

const letter = defineModel<string>('letter', { required: true })
const grade = defineModel<number>('grade', { required: true })

const { t } = useI18n()

const sizeForLookup = computed(() => props.size ?? 0)

// A letter with no grade at the current size stays listed but disabled, so
// the list does not jump around while the size is typed.
const letterOptions = computed(() => {
  const letters: readonly string[] = props.part === 'hole' ? HOLE_LETTERS : SHAFT_LETTERS
  return letters.map((value) => ({
    value,
    disabled: availableGrades(props.part, value, sizeForLookup.value).length === 0,
  }))
})

const gradeOptions = computed(() => {
  const available = availableGrades(props.part, letter.value, sizeForLookup.value)
  return ALL_GRADES.map((value) => ({ value, disabled: !available.includes(value) }))
})

const labelKey = computed(() => (props.part === 'hole' ? 'hole' : 'shaft'))
</script>

<template>
  <div class="class-picker" :class="`class-picker--${part}`">
    <span :id="`fit-${part}-label`" class="class-picker-label">
      {{ t(`tools.fitCalculator.${labelKey}`) }}
    </span>
    <div class="class-picker-selects">
      <Select
        v-model="letter"
        :options="letterOptions"
        option-label="value"
        option-value="value"
        option-disabled="disabled"
        :aria-label="t(`tools.fitCalculator.${labelKey}Letter`)"
        :data-testid="`fit-${part}-letter`"
        class="class-picker-select"
      />
      <Select
        v-model="grade"
        :options="gradeOptions"
        option-label="value"
        option-value="value"
        option-disabled="disabled"
        :aria-label="t(`tools.fitCalculator.${labelKey}Grade`)"
        :data-testid="`fit-${part}-grade`"
        class="class-picker-select"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.class-picker {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.class-picker-label {
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.class-picker--hole .class-picker-label {
  color: var(--p-blue-500);
}

.class-picker--shaft .class-picker-label {
  color: var(--p-orange-500);
}

.class-picker-selects {
  display: flex;
  gap: var(--space-1);
}

.class-picker-select {
  min-width: 5rem;
}
</style>
