<script setup lang="ts">
/**
 * What the QA engineer checks and under which instructions: the inspection
 * method with its description, the planner's notes on the step and the
 * order, who started the task and when, and whatever currently stops them
 * from recording a result.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatDateTimeOrDash } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

import type { LotStepResponse, ProductionOrderResponse } from '@/features/production'
import type { InspectionMethodResponse } from '@/features/inspection-methods'
import { useLocalizedText } from '@/shared/composables/useLocalizedText'
import { localizeLabel } from '@/shared/utils/localizeLabel'

const props = defineProps<{
  order: ProductionOrderResponse
  inspectionStep: LotStepResponse | null
  /** null while the method list loads, or for a method it does not hold. */
  method: InspectionMethodResponse | null
  canRecord: boolean
  evidenceBlocking: boolean
  waitingOnUpstream: boolean
}>()

const { t } = useI18n()
const { localize } = useLocalizedText()

const requiresEvidence = computed(
  () => props.inspectionStep?.inspection_method_requires_evidence === true,
)
const instructions = computed(() => localize(props.method?.description).trim() || null)
const stepNote = computed(() => props.inspectionStep?.note?.trim() || null)
const orderNote = computed(() => props.order.note?.trim() || null)
</script>

<template>
  <Panel :header="t('productionQa.detail.inspection')">
    <div class="detail-grid">
      <div class="field">
        <span class="field-label">{{ t('productionQa.detail.method') }}</span>
        <span class="field-value">{{
          localizeLabel(inspectionStep?.inspection_method_name) || getEmptyPlaceholder()
        }}</span>
      </div>
      <div class="field">
        <span class="field-label">{{ t('productionQa.detail.evidenceRequired') }}</span>
        <span class="field-value">{{ requiresEvidence ? t('common.yes') : t('common.no') }}</span>
      </div>
      <div class="field">
        <span class="field-label">{{ t('productionQa.detail.startedBy') }}</span>
        <span class="field-value">{{
          order.started_operator?.full_name ?? getEmptyPlaceholder()
        }}</span>
      </div>
      <div class="field">
        <span class="field-label">{{ t('productionQa.detail.startedAt') }}</span>
        <span class="field-value">{{ formatDateTimeOrDash(order.actual_start) }}</span>
      </div>
      <div class="field">
        <span class="field-label">{{ t('productionQa.detail.finishedAt') }}</span>
        <span class="field-value">{{ formatDateTimeOrDash(order.actual_end) }}</span>
      </div>
    </div>

    <div v-if="instructions" class="text-block">
      <span class="field-label">{{ t('productionQa.detail.instructions') }}</span>
      <p class="text-value">{{ instructions }}</p>
    </div>
    <div v-if="stepNote" class="text-block">
      <span class="field-label">{{ t('productionQa.detail.stepNote') }}</span>
      <p class="text-value">{{ stepNote }}</p>
    </div>
    <div v-if="orderNote" class="text-block">
      <span class="field-label">{{ t('productionQa.detail.orderNote') }}</span>
      <p class="text-value">{{ orderNote }}</p>
    </div>

    <!-- The things that stop a QA engineer finishing, stated up front
         rather than discovered at submit. -->
    <Message v-if="!canRecord" severity="secondary" :closable="false" class="notice">
      {{ t('productionQa.detail.recordPermissionTooltip') }}
    </Message>
    <Message v-else-if="evidenceBlocking" severity="warn" :closable="false" class="notice">
      {{ t('productionQa.detail.evidenceBlocking') }}
    </Message>
    <Message v-else-if="waitingOnUpstream" severity="info" :closable="false" class="notice">
      {{ t('productionQa.detail.notStartable') }}
    </Message>
  </Panel>
</template>

<style scoped lang="scss">
.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(9rem, 1fr));
  gap: var(--space-3) var(--space-5);
}

.field {
  min-width: 0;
}

.field-value {
  font-size: var(--font-size-sm);
}

.text-block {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin-top: var(--space-4);
}

// Kept as typed, since instructions and notes are often lists.
.text-value {
  margin: 0;
  font-size: var(--font-size-sm);
  white-space: pre-wrap;
}

.notice {
  margin-top: var(--space-4);
}
</style>
