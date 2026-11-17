<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { hasAction } from '@/core/utils/lifecycleActions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { isSourceApprovalPending, isSourceApprovalRejected } from '../../utils/lotSourceEligibility'

import type { LotSummaryResponse } from '../../../types/productionLotsResponse'
import { DEMAND_STATUS_SEVERITY } from '@/core/utils/demandStatus'

const props = defineProps<{
  lot: LotSummaryResponse
  canManage: boolean
  approvingSourceLotId: number | null
}>()

const emit = defineEmits<{
  approve: [lot: LotSummaryResponse]
  reject: [lot: LotSummaryResponse]
}>()

const { t } = useI18n()
const { missing } = useMissingPermission()

// The server offers a decision only while the lot and its source allow it;
// without manage:lots the offered buttons stay visible but disabled.
const canApproveNow = computed(() => hasAction(props.lot, 'approve_source'))
const canRejectNow = computed(() => hasAction(props.lot, 'reject_source'))
const decisionBlocked = computed(() => (props.canManage ? '' : missing(Permission.MANAGE_LOTS)))

function approve(): void {
  emit('approve', props.lot)
}

function reject(): void {
  emit('reject', props.lot)
}
</script>

<template>
  <div v-if="isSourceApprovalPending(lot) || isSourceApprovalRejected(lot)" class="approval-cell">
    <Tag
      v-if="isSourceApprovalRejected(lot)"
      :value="t('production.lots.detail.record.sourceApproval.rejected')"
      severity="danger"
      data-testid="source-approval-tag"
      v-tooltip.top="
        t('production.lots.detail.record.sourceApproval.rejectedTooltip', {
          reason: lot.source_rejection_reason ?? '',
        })
      "
    />
    <Tag
      v-else-if="!canManage || !canApproveNow"
      :value="t('production.lots.detail.record.sourceApproval.pending')"
      severity="warn"
      data-testid="source-approval-tag"
      v-tooltip.top="t('production.lots.detail.record.sourceApproval.pendingTooltip')"
    />
    <span
      v-if="canApproveNow"
      v-tooltip.top="decisionBlocked || t('production.lots.detail.record.sourceApproval.approve')"
    >
      <Button
        icon="mdi mdi-check"
        size="small"
        text
        severity="success"
        data-testid="source-approve"
        :disabled="!canManage || approvingSourceLotId === lot.id"
        :aria-label="t('production.lots.detail.record.sourceApproval.approve')"
        @click.stop="approve"
      />
    </span>
    <span
      v-if="canRejectNow"
      v-tooltip.top="decisionBlocked || t('production.lots.detail.record.sourceApproval.reject')"
    >
      <Button
        icon="mdi mdi-close"
        size="small"
        text
        severity="danger"
        data-testid="source-reject"
        :disabled="!canManage"
        :aria-label="t('production.lots.detail.record.sourceApproval.reject')"
        @click.stop="reject"
      />
    </span>
  </div>
  <template v-else>
    <Tag
      v-if="lot.demand_status"
      :value="t(`sourceItems.demands.status.${lot.demand_status}`)"
      :severity="DEMAND_STATUS_SEVERITY[lot.demand_status]"
    />
    <span v-else class="source-label">{{ getEmptyPlaceholder() }}</span>
  </template>
</template>

<style scoped lang="scss">
.approval-cell {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

// Matches the source columns' placeholder styling.
.source-label {
  font-size: var(--font-size-sm);
  font-weight: 600;
}
</style>
