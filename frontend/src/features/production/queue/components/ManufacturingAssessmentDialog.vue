<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { useProductionQueueStore } from '../../stores/productionQueueStore'
import { MANUFACTURING_COMPLEXITIES } from '../../utils/productionOrderStatus'

import type { InputNumberInputEvent } from 'openvue/inputnumber'
import type {
  ManufacturingComplexity,
  ProductionOrderResponse,
} from '../../types/productionOrdersResponse'

const props = defineProps<{
  order: ProductionOrderResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const store = useProductionQueueStore()

const actualMinutesPerPiece = ref<number | null>(null)
const actualSetupMinutes = ref<number | null>(null)
// Rubrics below are deliberately simple placeholders, the shop team
// can refine the wording once real assessment data starts coming in.
const complexity = ref<ManufacturingComplexity>('normal')
const note = ref('')
const { submitting, errorMessage, run } = useSubmitAction()

const complexityOptions = computed(() =>
  MANUFACTURING_COMPLEXITIES.map((c) => ({
    value: c,
    label: t(`productionAssessment.complexity.${c}`),
    rubric: t(`productionAssessment.rubric.${c}`),
  })),
)

watch(visible, (isVisible) => {
  if (!isVisible) return
  actualMinutesPerPiece.value = null
  actualSetupMinutes.value = null
  complexity.value = 'normal'
  note.value = ''
  errorMessage.value = null
})

const isValid = computed(
  () => actualMinutesPerPiece.value !== null && actualMinutesPerPiece.value >= 0,
)

// InputNumber writes its model only when the field loses focus, so the
// required minutes follow every keystroke instead, and Save is enabled as
// soon as what is typed is valid.
function onMinutesInput(event: InputNumberInputEvent): void {
  actualMinutesPerPiece.value = typeof event.value === 'number' ? event.value : null
}

function onSkip(): void {
  visible.value = false
}

async function onSubmit(): Promise<void> {
  const order = props.order
  if (!order || !isValid.value) {
    errorMessage.value = t('productionAssessment.errors.invalid')
    return
  }

  await run(async () => {
    await store.recordAssessment(order.id, {
      actual_minutes_per_piece: actualMinutesPerPiece.value!,
      actual_setup_minutes: actualSetupMinutes.value ?? undefined,
      complexity: complexity.value,
      note: note.value.trim() || undefined,
    })
    visible.value = false
  }, t('productionAssessment.errors.unknown'))
}

defineExpose({ actualMinutesPerPiece, actualSetupMinutes, complexity, isValid, onSkip })
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :closable="false"
    :header="t('productionAssessment.title')"
    :style="{ width: 'var(--dialog-width-sm)' }"
  >
    <div v-if="order" class="assessment-form">
      <p class="description">{{ t('productionAssessment.description') }}</p>

      <div class="field">
        <label :for="`${uid}-actual-minutes-per-piece`">
          {{ t('productionAssessment.fields.actualMinutesPerPiece') }} *
        </label>
        <InputNumber
          v-model="actualMinutesPerPiece"
          :input-id="`${uid}-actual-minutes-per-piece`"
          :min="0"
          :max-fraction-digits="2"
          :step="0.01"
          fluid
          @input="onMinutesInput"
        />
      </div>

      <div class="field">
        <label :for="`${uid}-actual-setup-minutes`">{{ t('productionAssessment.fields.actualSetupMinutes') }}</label>
        <InputNumber v-model="actualSetupMinutes" :input-id="`${uid}-actual-setup-minutes`" :min="0" fluid />
      </div>

      <div class="field">
        <!-- eslint-disable-next-line vuejs-accessibility/label-has-for -- captions the group below, which names it through aria-labelledby -->
        <label :id="`${uid}-complexity`">{{ t('productionAssessment.fields.complexity') }}</label>
        <div role="group" :aria-labelledby="`${uid}-complexity`" class="complexity-options">
          <div
            v-for="option in complexityOptions"
            :key="option.value"
            class="complexity-option"
            v-tooltip.top="option.rubric"
          >
            <RadioButton
              v-model="complexity"
              :input-id="`complexity-${option.value}`"
              :value="option.value"
              name="complexity"
            />
            <label :for="`complexity-${option.value}`">{{ option.label }}</label>
          </div>
        </div>
      </div>

      <div class="field">
        <label :for="`${uid}-note`">{{ t('productionAssessment.fields.note') }}</label>
        <Textarea v-model="note" :id="`${uid}-note`" rows="2" auto-resize fluid />
      </div>

      <Message v-if="errorMessage" severity="error" :closable="false">
        {{ errorMessage }}
      </Message>
    </div>

    <template #footer>
      <Button
        :label="t('productionAssessment.skip')"
        severity="secondary"
        outlined
        :disabled="submitting"
        @click="onSkip"
      />
      <Button
        :label="t('productionAssessment.submit')"
        :loading="submitting"
        :disabled="!isValid"
        @click="onSubmit"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.assessment-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.description {
  margin: 0;
  color: var(--p-text-muted-color);
}

.complexity-options {
  display: flex;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.complexity-option {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}
</style>
