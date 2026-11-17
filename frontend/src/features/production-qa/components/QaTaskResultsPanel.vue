<script setup lang="ts">
/**
 * The recorded outcome of a QA task: the totals across every recording and
 * each recording on its own, with who inspected, who entered it and why
 * pieces were scrapped.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatDateOrDash } from '@/core/utils/dates'
import { formatDecimal } from '@/core/utils/numbers'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { scrapReasonLabelKey } from '@/shared/utils/scrapReasons'

import type { ProductionOrderCompletionResponse } from '@/features/production'

const props = defineProps<{
  completions: ProductionOrderCompletionResponse[]
}>()

const { t } = useI18n()

const totals = computed(() =>
  props.completions.reduce(
    (sum, c) => ({
      accepted: sum.accepted + c.quantity_accepted,
      rejected: sum.rejected + c.quantity_rejected,
      rework: sum.rework + c.quantity_rework,
      scrap: sum.scrap + c.quantity_scrap,
    }),
    { accepted: 0, rejected: 0, rework: 0, scrap: 0 },
  ),
)

// Rework and scrap only appear when a recording has them, so a clean pass
// reads as one short line.
function breakdown(c: ProductionOrderCompletionResponse): string {
  const parts = [
    `${formatDecimal(c.quantity_accepted)} ${t('productionQa.detail.results.accepted')}`,
    `${formatDecimal(c.quantity_rejected)} ${t('productionQa.detail.results.rejected')}`,
  ]
  if (c.quantity_rework > 0) {
    parts.push(`${formatDecimal(c.quantity_rework)} ${t('productionQa.detail.results.rework')}`)
  }
  if (c.quantity_scrap > 0) {
    const reason = c.scrap_reason ? ` (${t(scrapReasonLabelKey(c.scrap_reason))})` : ''
    parts.push(`${formatDecimal(c.quantity_scrap)} ${t('productionQa.detail.results.scrap')}${reason}`)
  }
  return parts.join(', ')
}
</script>

<template>
  <Panel :header="t('productionQa.detail.results.title')">
    <div v-if="completions.length === 0" class="empty-note">
      {{ t('productionQa.detail.results.empty') }}
    </div>

    <template v-else>
      <div class="totals">
        <div class="field">
          <span class="field-label">{{ t('productionQa.detail.results.accepted') }}</span>
          <span class="total-value total-accepted">{{ formatDecimal(totals.accepted) }}</span>
        </div>
        <div class="field">
          <span class="field-label">{{ t('productionQa.detail.results.rejected') }}</span>
          <span class="total-value" :class="{ 'total-rejected': totals.rejected > 0 }">{{
            formatDecimal(totals.rejected)
          }}</span>
        </div>
        <div class="field">
          <span class="field-label">{{ t('productionQa.detail.results.rework') }}</span>
          <span class="total-value">{{ formatDecimal(totals.rework) }}</span>
        </div>
        <div class="field">
          <span class="field-label">{{ t('productionQa.detail.results.scrap') }}</span>
          <span class="total-value">{{ formatDecimal(totals.scrap) }}</span>
        </div>
      </div>

      <ul class="recordings">
        <li v-for="c in completions" :key="c.id" class="recording">
          <div class="recording-head">
            <span class="recording-date">{{ formatDateOrDash(c.completion_date) }}</span>
            <span>{{ c.operator?.full_name ?? getEmptyPlaceholder() }}</span>
            <span v-if="c.recorded_by_id !== c.operator_id" class="muted">
              {{
                t('productionQa.detail.results.recordedBy', {
                  name: c.recorded_by?.full_name ?? getEmptyPlaceholder(),
                })
              }}
            </span>
            <span class="recording-quantity">{{ formatDecimal(c.quantity) }}</span>
          </div>
          <span class="muted">{{ breakdown(c) }}</span>
          <span v-if="c.note" class="recording-note">{{ c.note }}</span>
        </li>
      </ul>
    </template>
  </Panel>
</template>

<style scoped lang="scss">
.totals {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3) var(--space-5);
}

.field {
  min-width: 0;
}

.total-value {
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.total-accepted {
  color: var(--p-green-600);
}

.total-rejected {
  color: var(--p-red-600);
}

.recordings {
  display: flex;
  flex-direction: column;
  margin: var(--space-4) 0 0;
  padding: 0;
  list-style: none;
}

.recording {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) 0;
  border-top: 1px solid var(--p-content-border-color);
  font-size: var(--font-size-sm);
}

.recording-head {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.recording-date {
  font-weight: 600;
}

.recording-quantity {
  margin-left: auto;
  font-weight: 600;
}

.muted {
  color: var(--p-text-muted-color);
}

.recording-note {
  white-space: pre-wrap;
}
</style>
