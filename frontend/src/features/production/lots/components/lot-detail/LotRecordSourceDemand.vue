<script lang="ts">
// Module-level so the ids are shared across instances. Allocation rows carry
// no unique id, so each object gets a stable id by reference for v-for keys.
import type { SourceItemAllocationResponse } from '@/features/source-items'

const allocationRowIds = new WeakMap<SourceItemAllocationResponse, number>()
let nextAllocationRowId = 0

function allocationRowId(alloc: SourceItemAllocationResponse): number {
  const existing = allocationRowIds.get(alloc)
  if (existing !== undefined) return existing
  const id = ++nextAllocationRowId
  allocationRowIds.set(alloc, id)
  return id
}
</script>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { hasAction } from '@/core/utils/lifecycleActions'
import { formatDecimal } from '@/core/utils/numbers'
import { formatISODateTime } from '@/core/utils/dates'
import { useUsersStore } from '@/core/stores/usersStore'
import UserAvatarPreview from '@/shared/components/user/UserAvatarPreview.vue'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import {
  canDemandSourceItem,
  isSourceApprovalPending,
  isSourceApprovalRejected,
} from '../../utils/lotSourceEligibility'

import type { LotResponse } from '../../../types/productionLotsResponse'
import type { SourceItemDemandResponse } from '@/features/source-items'
import type { SourceItemDemandSummaryResponse } from '@/features/source-items'
import type { OrderResponse } from '@/features/orders'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { DEMAND_STATUS_SEVERITY } from '@/core/utils/demandStatus'

const props = withDefaults(
  defineProps<{
    lot: LotResponse
    sourceItemDemand: SourceItemDemandResponse | null
    sourceItemDemandArrived: number
    summary: SourceItemDemandSummaryResponse | null
    allocations: SourceItemAllocationResponse[]
    sourceOrder: OrderResponse | null
    manageMode: boolean
    canWrite: boolean
    // Gates Approve and Reject.
    canApprove?: boolean
    // An approval is being sent, so Approve shows it and takes no click.
    approving?: boolean
  }>(),
  { canApprove: false, approving: false },
)

defineEmits<{
  'view-demand': []
  'create-demand': []
  'approve-source': []
  'reject-source': []
}>()

const { t } = useI18n()
const usersStore = useUsersStore()

// Each allocation paired with its order line item, when resolvable.
const allocationRows = computed(() => {
  const itemsById = new Map((props.sourceOrder?.items ?? []).map((i) => [i.id, i]))
  return props.allocations.map((alloc) => ({
    id: allocationRowId(alloc),
    alloc,
    item: alloc.order_item_id !== null ? (itemsById.get(alloc.order_item_id) ?? null) : null,
  }))
})

// A lot without a bought or source item source (e.g. rework) cannot demand
// a source item; the backend would reject it.
const canDemand = computed(() => canDemandSourceItem(props.lot))

// Only shown while there is no demand. Approved also appears there when the
// demand was canceled, since the approval decision is kept.
const isPending = computed(() => isSourceApprovalPending(props.lot))
const isRejected = computed(() => isSourceApprovalRejected(props.lot))
const isApproved = computed(() => props.lot.source_approval_status === 'approved')

// The server offers a decision only while the lot and its source allow it;
// without manage:lots the offered buttons stay visible but disabled.
const { missing } = useMissingPermission()
const approveOffered = computed(() => hasAction(props.lot, 'approve_source'))
const rejectOffered = computed(() => hasAction(props.lot, 'reject_source'))
const decisionBlocked = computed(() => (props.canApprove ? '' : missing(Permission.MANAGE_LOTS)))

// The approval user ids come as bare ids.
function resolveUser(id: number | null | undefined) {
  return id === null || id === undefined ? null : (usersStore.getById(id) ?? null)
}
const approvedByUser = computed(() => resolveUser(props.lot.source_approved_by_id))
const rejectedByUser = computed(() => resolveUser(props.lot.source_rejected_by_id))

const approvedOnText = computed(() =>
  props.lot.source_approved_date ? formatISODateTime(props.lot.source_approved_date) : null,
)
const rejectedOnText = computed(() =>
  props.lot.source_rejected_date ? formatISODateTime(props.lot.source_rejected_date) : null,
)

const rejectedTooltip = computed(() =>
  t('production.lots.detail.record.sourceApproval.rejectedTooltip', {
    reason: props.lot.source_rejection_reason ?? '',
  }),
)
</script>

<template>
  <div class="source-demand-section">
    <span class="section-label">{{ t('production.lots.detail.record.sourceDemand.title') }}</span>

    <div v-if="!lot.input_demand_id" class="demand-empty">
      <!-- Pending: an approver gets Approve and Reject, anyone else sees the
           tag next to them, and so does everyone once the lot is finished. -->
      <template v-if="isPending">
        <Tag
          v-if="!canApprove || !approveOffered"
          class="approval-tag"
          :value="t('production.lots.detail.record.sourceApproval.pending')"
          severity="warn"
          v-tooltip.top="t('production.lots.detail.record.sourceApproval.pendingTooltip')"
        />
        <div class="hint">
          {{ t('production.lots.detail.record.sourceApproval.noDemandUntilApproved') }}
        </div>
      </template>

      <!-- Rejected: the reason is a tooltip and is also spelled out below. -->
      <template v-else-if="isRejected">
        <Tag
          class="approval-tag"
          :value="t('production.lots.detail.record.sourceApproval.rejected')"
          severity="danger"
          v-tooltip.top="rejectedTooltip"
        />
        <div class="detail-grid approval-grid">
          <div class="field">
            <span class="field-label">{{
              t('production.lots.detail.record.sourceApproval.rejectedBy')
            }}</span>
            <UserAvatarPreview :user="rejectedByUser" />
          </div>
          <div class="field">
            <span class="field-label">{{
              t('production.lots.detail.record.sourceApproval.rejectedOn')
            }}</span>
            <span class="field-value">{{ rejectedOnText ?? getEmptyPlaceholder() }}</span>
          </div>
          <div class="field field-wide">
            <span class="field-label">{{
              t('production.lots.detail.record.sourceApproval.reason')
            }}</span>
            <span class="field-value field-note">{{
              lot.source_rejection_reason || getEmptyPlaceholder()
            }}</span>
          </div>
        </div>
      </template>

      <!-- Approved without a demand: the demand was canceled after approval. -->
      <template v-else-if="isApproved">
        <div class="detail-grid approval-grid">
          <div class="field">
            <span class="field-label">{{
              t('production.lots.detail.record.sourceApproval.approvedBy')
            }}</span>
            <UserAvatarPreview :user="approvedByUser" />
          </div>
          <div class="field">
            <span class="field-label">{{
              t('production.lots.detail.record.sourceApproval.approvedOn')
            }}</span>
            <span class="field-value">{{ approvedOnText ?? getEmptyPlaceholder() }}</span>
          </div>
        </div>
      </template>

      <div class="empty-note">{{ t('production.lots.detail.record.sourceDemand.none') }}</div>
      <div v-if="!lot.is_alteration && !canDemand" class="hint">
        {{ t('production.lots.detail.record.sourceDemand.notPlannedWithoutSource') }}
      </div>
      <div
        v-if="approveOffered || rejectOffered || (manageMode && !lot.is_alteration)"
        class="manage-actions"
      >
        <span v-if="approveOffered" v-tooltip.top="decisionBlocked || undefined">
          <Button
            :label="t('production.lots.detail.record.sourceApproval.approve')"
            icon="mdi mdi-check"
            size="small"
            severity="success"
            data-testid="source-approve"
            :disabled="!canApprove"
            :loading="approving"
            @click="$emit('approve-source')"
          />
        </span>
        <span v-if="rejectOffered" v-tooltip.top="decisionBlocked || undefined">
          <Button
            :label="t('production.lots.detail.record.sourceApproval.reject')"
            icon="mdi mdi-close"
            size="small"
            severity="danger"
            outlined
            data-testid="source-reject"
            :disabled="!canApprove"
            @click="$emit('reject-source')"
          />
        </span>
        <Button
          v-if="manageMode && !lot.is_alteration"
          :label="t('production.lots.detail.rawMaterial.createDemand')"
          icon="mdi mdi-plus"
          size="small"
          severity="secondary"
          outlined
          :disabled="!canWrite || !canDemand"
          v-tooltip.top="
            !canDemand ? t('production.lots.detail.rawMaterial.noMaterialSource') : undefined
          "
          @click="$emit('create-demand')"
        />
      </div>
    </div>

    <div v-else class="demand-block">
      <div v-if="sourceItemDemand" class="detail-grid">
        <div class="field">
          <span class="field-label">{{
            t('production.lots.detail.record.sourceDemand.status')
          }}</span>
          <Tag
            class="field-link"
            role="button"
            tabindex="0"
            :value="t(`sourceItems.demands.status.${sourceItemDemand.status}`)"
            :severity="DEMAND_STATUS_SEVERITY[sourceItemDemand.status]"
            @click="$emit('view-demand')"
            @keydown.enter="$emit('view-demand')"
          />
        </div>
        <!-- The demand exists, so the approval is shown as a record. -->
        <template v-if="lot.source_approval_status === 'approved'">
          <div class="field">
            <span class="field-label">{{
              t('production.lots.detail.record.sourceApproval.approvedBy')
            }}</span>
            <UserAvatarPreview :user="approvedByUser" />
          </div>
          <div class="field">
            <span class="field-label">{{
              t('production.lots.detail.record.sourceApproval.approvedOn')
            }}</span>
            <span class="field-value">{{ approvedOnText ?? getEmptyPlaceholder() }}</span>
          </div>
        </template>
        <div class="field">
          <span class="field-label">{{
            t('production.lots.detail.record.sourceDemand.arrived')
          }}</span>
          <span class="field-value"
            >{{ formatDecimal(sourceItemDemandArrived) }} /
            {{ formatDecimal(sourceItemDemand.quantity) }} {{ sourceItemDemand.unit }}</span
          >
        </div>
        <div class="field">
          <span class="field-label">{{
            t('production.lots.detail.record.sourceDemand.requestedBy')
          }}</span>
          <span class="field-value">{{
            sourceItemDemand.creator?.full_name ?? getEmptyPlaceholder()
          }}</span>
        </div>
        <div class="field">
          <span class="field-label">{{
            t('production.lots.detail.record.sourceDemand.requested')
          }}</span>
          <span class="field-value">{{ sourceItemDemand.created }}</span>
        </div>
        <template v-if="summary">
          <div class="field">
            <span class="field-label">{{
              t('production.lots.detail.record.sourceDemand.allocated')
            }}</span>
            <span class="field-value"
              >{{ formatDecimal(summary.allocated) }} / {{ formatDecimal(summary.total) }}</span
            >
          </div>
          <div class="field">
            <span class="field-label">{{
              t('production.lots.detail.record.sourceDemand.ordered')
            }}</span>
            <span class="field-value">{{ formatDecimal(summary.ordered) }}</span>
          </div>
          <div class="field">
            <span class="field-label">{{
              t('production.lots.detail.record.sourceDemand.inTransit')
            }}</span>
            <span class="field-value">{{ formatDecimal(summary.in_transit) }}</span>
          </div>
          <div class="field">
            <span class="field-label">{{
              t('production.lots.detail.record.sourceDemand.delivered')
            }}</span>
            <span class="field-value">{{ formatDecimal(summary.delivered) }}</span>
          </div>
          <div class="field">
            <span class="field-label">{{
              t('production.lots.detail.record.sourceDemand.fromStock')
            }}</span>
            <span class="field-value">{{ formatDecimal(summary.fulfilled_from_stock) }}</span>
          </div>
          <div class="field">
            <span class="field-label">{{
              t('production.lots.detail.record.sourceDemand.unallocated')
            }}</span>
            <span class="field-value">{{ formatDecimal(summary.unallocated) }}</span>
          </div>
        </template>
        <div class="field">
          <span class="field-label">{{
            t('production.lots.detail.record.sourceDemand.desiredBy')
          }}</span>
          <span class="field-value">{{
            sourceItemDemand.desired_delivery_date ?? getEmptyPlaceholder()
          }}</span>
        </div>
        <div class="field">
          <span class="field-label">{{
            t('production.lots.detail.record.sourceDemand.itemsPerUnit')
          }}</span>
          <span class="field-value">{{ formatDecimal(sourceItemDemand.items_per_unit) }}</span>
        </div>
        <div v-if="sourceItemDemand.high_priority" class="field">
          <span class="field-label">{{
            t('production.lots.detail.record.sourceDemand.priority')
          }}</span>
          <Tag
            :value="t('production.lots.detail.record.demands.highPriority')"
            severity="danger"
            icon="mdi mdi-arrow-up-bold"
          />
        </div>
        <div v-if="sourceItemDemand.notify_on_delivery" class="field">
          <span class="field-label">{{
            t('production.lots.detail.record.sourceDemand.notify')
          }}</span>
          <span class="field-value"><i class="mdi mdi-bell-outline" aria-hidden="true" /></span>
        </div>
        <div v-if="sourceItemDemand.note" class="field field-wide">
          <span class="field-label">{{
            t('production.lots.detail.record.sourceDemand.note')
          }}</span>
          <span class="field-value field-note">{{ sourceItemDemand.note }}</span>
        </div>
      </div>
      <span v-else class="field-value">
        {{ t('production.lots.detail.rawMaterial.demandLinked', { id: lot.input_demand_id }) }}
      </span>

      <div v-if="allocationRows.length" class="allocation-list">
        <div v-for="row in allocationRows" :key="row.id" class="order-card">
          <div class="order-card-header">
            <Tag
              :value="
                t(`production.lots.detail.record.sourceDemand.allocationSource.${row.alloc.source}`)
              "
              severity="secondary"
            />
            <span v-if="row.alloc.order_number" class="field-value"
              >{{ row.alloc.order_number }} · {{ row.alloc.order_supplier_name }}</span
            >
            <span class="allocation-qty">{{ formatDecimal(row.alloc.quantity) }}</span>
          </div>
          <div v-if="row.item" class="order-dates">
            <span class="field-sublabel">
              {{ t('production.lots.detail.record.orderDetail.orderedBy') }}:
              {{
                row.item.orderer?.full_name ?? row.item.creator?.full_name ?? getEmptyPlaceholder()
              }}
              <template v-if="row.item.ordered_date">
                ({{ formatISODateTime(row.item.ordered_date) }})
              </template>
            </span>
            <span class="field-sublabel">
              {{ t('production.lots.detail.record.orderDetail.plannedDelivery') }}:
              {{ row.item.expected_delivery_date ?? getEmptyPlaceholder() }}
            </span>
            <span v-if="row.item.expected_pickup_date" class="field-sublabel">
              {{ t('production.lots.detail.record.orderDetail.plannedPickup') }}:
              {{ row.item.expected_pickup_date }}
            </span>
            <span v-if="row.item.delivery_date" class="field-sublabel">
              {{ t('production.lots.detail.record.orderDetail.delivered') }}:
              {{ formatISODateTime(row.item.delivery_date) }}
            </span>
          </div>
        </div>
      </div>

      <!-- Fallback when allocations have no order item yet but the lot's
           denormalized fields do. -->
      <div v-else-if="lot.source_order_number" class="order-card">
        <div class="order-card-header">
          <span class="field-value">{{
            t('production.lots.detail.audit.source.order', { number: lot.source_order_number })
          }}</span>
        </div>
        <div class="order-dates">
          <span v-if="lot.source_delivery_date" class="field-sublabel">
            {{ t('production.lots.detail.audit.source.actualDelivery') }}:
            {{ formatISODateTime(lot.source_delivery_date) }}
          </span>
          <span v-else-if="lot.source_expected_delivery_date" class="field-sublabel">
            {{ t('production.lots.detail.audit.source.expectedDelivery') }}:
            {{ lot.source_expected_delivery_date }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(8.5rem, 1fr));
  gap: var(--space-3) var(--space-5);
}

.field {
  min-width: 0;
}

.field-wide {
  grid-column: 1 / -1;
}

.field-value {
  font-size: var(--font-size-sm);
}

.field-note {
  white-space: pre-line;
}

.field-link {
  cursor: pointer;

  &:hover {
    opacity: 0.85;
  }
}

.source-demand-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.section-label {
  font-size: var(--font-size-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--p-text-muted-color);
}

.demand-empty {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.approval-tag {
  width: fit-content;
}

.approval-grid {
  margin: 0;
}

.hint {
  font-size: var(--font-size-xs);
}

.field-value {
  font-size: var(--font-size-sm);
}

.field-sublabel {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.demand-block {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.allocation-list {
  margin-top: var(--space-1);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.allocation-qty {
  margin-left: auto;
  font-variant-numeric: tabular-nums;
  color: var(--p-text-muted-color);
}

.manage-actions {
  display: flex;
  gap: var(--space-2);
}

.order-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.order-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.order-dates {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
</style>
