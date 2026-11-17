<script setup lang="ts">
// Step table of a production lot, grouped into one banded block per
// position. Each edit is written immediately, or in staged mode emitted as
// an intent so the host can hold a draft and save the structure at once.
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { usePermissions } from '@/core/composables/usePermissions'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { Permission } from '@/core/auth/permissions'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { useFabricationMethodsStore } from '@/features/fabrication-methods'
import { useInspectionMethodsStore } from '@/features/inspection-methods'
import { OrderCreateForm, OrderDetailDialog } from '@/features/orders'
import EmptyState from '@/shared/components/EmptyState.vue'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { useProductionQueueStore } from '../../stores/productionQueueStore'
import ProductionOrderCompletionDialog from '../../components/ProductionOrderCompletionDialog.vue'
import SetPlannedDateDialog from './SetPlannedDateDialog.vue'
import DeliveryDateCell from './DeliveryDateCell.vue'
import LotStepPositionCell from './LotStepPositionCell.vue'
import LotStepMethodCell from './LotStepMethodCell.vue'
import LotStepMachineCell from './LotStepMachineCell.vue'
import { useLotStepAssignment } from '../composables/useLotStepAssignment'
import { useLotStepPlanning } from '../composables/useLotStepPlanning'
import { useLotStepEditing } from '../composables/useLotStepEditing'
import { useLotStepContextMenu } from '../composables/useLotStepContextMenu'

import type {
  AppendedStep,
  LotStepPatch,
  PendingAssignments,
  PendingReassignments,
} from '../composables/useLotStructureDraft'
import type { LotPositionResponse, LotStepResponse } from '../../types/productionLotsResponse'
import { sortedBySequence } from '../../utils/sequence'

const props = defineProps<{
  lotId: number
  steps: LotStepResponse[]
  positions: LotPositionResponse[]
  madeItemId: number
  madeItemPartNumber: string
  madeItemRevision: string
  madeItemArticleName: string
  readonly: boolean
  // Staged mode emits every edit as an intent instead of writing it.
  staged?: boolean
  // Staged mode only: the picks the host's draft currently holds, keyed by
  // draft position id and production order id respectively.
  pendingAssignments?: PendingAssignments
  pendingReassignments?: PendingReassignments
}>()

const emit = defineEmits<{
  editStep: [stepId: number, patch: LotStepPatch]
  removeStep: [stepId: number]
  appendStep: [step: AppendedStep]
  reorderPositions: [orderedPositionIds: number[]]
  assignPosition: [positionId: number, key: string]
  clearAssignment: [positionId: number]
  reassignOrder: [orderId: number, key: string | null]
  clearReassignment: [orderId: number]
}>()

const { t } = useI18n()
const { toastOnError } = useErrorToast()
const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const fabricationMethodsStore = useFabricationMethodsStore()
const inspectionMethodsStore = useInspectionMethodsStore()
const queueStore = useProductionQueueStore()

const rows = computed(() => sortedBySequence(props.steps))

const positionsById = computed<Map<number, LotPositionResponse>>(
  () => new Map(props.positions.map((p) => [p.id, p])),
)

function positionForStep(step: LotStepResponse): LotPositionResponse | undefined {
  return positionsById.value.get(step.position_id)
}

function groupStepCount(positionId: number): number {
  return rows.value.filter((s) => s.position_id === positionId).length
}

const {
  machines,
  loadingMachines,
  loadMachines,
  pools,
  loadingPools,
  loadPools,
  orders,
  loadingOrders,
  loadOrders,
  assigningOrderId,
  onReassignChange,
  assigningPositionId,
  showCreateOrder,
  showOrderDetail,
  orderDetailOrderId,
  createOrderPresetSupplierId,
  openOrderDetail,
  onAssignTargetChange,
  onOrderCreated,
} = useLotStepAssignment(props, positionsById, {
  assignPosition: (positionId, key) => emit('assignPosition', positionId, key),
  clearAssignment: (positionId) => emit('clearAssignment', positionId),
  reassignOrder: (orderId, key) => emit('reassignOrder', orderId, key),
  clearReassignment: (orderId) => emit('clearReassignment', orderId),
})

const {
  plannedInfoFor,
  plannedEditTarget,
  showSetPlannedDate,
  plannedDateEditTarget,
  openSetPlannedDate,
  onPlannedDateSaved,
  completableOrder,
  canCompletePosition,
  showCompletion,
  completionTarget,
  completionSteps,
  openCompletion,
  onCompletionRecorded,
} = useLotStepPlanning(props)

const { onFieldChange, removeStep, addStep, addInspectionStep, onRowReorder } = useLotStepEditing(
  props,
  rows,
  {
    editStep: (stepId, patch) => emit('editStep', stepId, patch),
    removeStep: (stepId) => emit('removeStep', stepId),
    appendStep: (step) => emit('appendStep', step),
    reorderPositions: (ids) => emit('reorderPositions', ids),
  },
)

const { cm, contextMenuItem, onRowContextMenu, contextMenuItems } = useLotStepContextMenu()

onMounted(() => {
  if (fabricationMethodsStore.items.length === 0) {
    void fabricationMethodsStore.refresh()
  }
  if (inspectionMethodsStore.items.length === 0) {
    void inspectionMethodsStore.refresh()
  }
  loadMachines().catch(toastOnError())
  loadPools().catch(toastOnError())
  if (queueStore.orders.length === 0) {
    queueStore.fetchOrders().catch(toastOnError())
  }
  if (!props.readonly && hasPermission(Permission.WRITE_ORDERS)) {
    loadOrders().catch(toastOnError())
  }
})

// A rowspan cell belongs to the group's first row, so the global row hover
// would leave a position's spanned cells untinted when a later step is
// hovered. OpenVue has no row mouse event, so the hovered row is resolved
// from the data-p-index attribute and the whole position is tinted.
const hoveredPositionId = ref<number | null>(null)

function onTableMouseOver(event: Event): void {
  const target = event.target as HTMLElement | null
  const row = target?.closest?.('tr[data-p-index]')
  const index = row ? Number(row.getAttribute('data-p-index')) : Number.NaN
  hoveredPositionId.value = Number.isNaN(index) ? null : (rows.value[index]?.position_id ?? null)
}

function rowClass(data: LotStepResponse): string | undefined {
  return data.position_id === hoveredPositionId.value ? 'position-row-hovered' : undefined
}

// Mirrors the backend's assignment guards. On an assigned position only a
// fabrication method change and deleting a step are blocked.
function isPositionUnassigned(step: LotStepResponse): boolean {
  return positionForStep(step)?.kind === 'unassigned'
}

function isMethodLocked(step: LotStepResponse): boolean {
  return step.role === 'fabrication' && !isPositionUnassigned(step)
}

const canReorder = computed(() => !props.readonly && props.positions.length > 1)
</script>

<template>
  <div class="step-list">
    <div class="step-list-header">
      <span class="step-list-title">{{ t('production.lots.detail.steps.title') }}</span>
      <div v-if="!readonly" class="step-list-actions compact-buttons">
        <Button
          :label="t('production.lots.detail.steps.add')"
          icon="mdi mdi-plus"
          size="small"
          severity="secondary"
          outlined
          @click="addStep"
        />
        <Button
          :label="t('production.lots.detail.steps.addInspection')"
          icon="mdi mdi-check-decagram"
          size="small"
          severity="secondary"
          outlined
          @click="addInspectionStep"
        />
      </div>
    </div>

    <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- tracks the hovered or focused row to highlight its position, not an interaction -->
    <div
      class="step-table"
      @mouseover="onTableMouseOver"
      @focusin="onTableMouseOver"
      @mouseleave="hoveredPositionId = null"
      @focusout="hoveredPositionId = null"
    >
    <DataTable
      :value="rows"
      :row-class="rowClass"
      v-model:context-menu-selection="contextMenuItem"
      size="small"
      data-key="id"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
      :reorderable-rows="canReorder"
      row-group-mode="rowspan"
      group-rows-by="position_id"
      @row-reorder="onRowReorder"
      @row-contextmenu="onRowContextMenu"
    >
      <!-- field="position_id" makes OpenVue span the drag handle and the
           position cell across the position's steps, so a position moves
           as a unit. -->
      <Column
        v-if="canReorder"
        row-reorder
        field="position_id"
        header-style="width: 2.5rem"
        :pt="{ reorderableRowHandle: { 'data-testid': 'step-reorder-handle' } }"
      />
      <Column
        field="position_id"
        :header="t('production.lots.detail.steps.position')"
        style="width: 7rem"
      >
        <template #body="{ data }">
          <LotStepPositionCell
            :position="positionsById.get((data as LotStepResponse).position_id)"
            :step-count="groupStepCount((data as LotStepResponse).position_id)"
          />
        </template>
      </Column>
      <Column
        :header="t('production.lots.detail.steps.method')"
        style="min-width: 12rem"
      >
        <template #body="{ data }">
          <LotStepMethodCell
            :step="data as LotStepResponse"
            :readonly="readonly"
            :locked="isMethodLocked(data as LotStepResponse)"
            @change="(patch) => onFieldChange(data as LotStepResponse, patch)"
          />
        </template>
      </Column>
      <Column :header="t('production.lots.detail.steps.machine')" style="min-width: 11rem">
        <template #body="{ data }">
          <LotStepMachineCell
            :key="positionForStep(data as LotStepResponse)?.id ?? 'none'"
            :position="positionForStep(data as LotStepResponse)"
            :readonly="readonly"
            :staged="staged"
            :pending-assignments="pendingAssignments"
            :pending-reassignments="pendingReassignments"
            :machines="machines"
            :pools="pools"
            :orders="orders"
            :loading-targets="loadingMachines || loadingPools"
            :loading-orders="loadingOrders"
            :assigning-order-id="assigningOrderId"
            :assigning-position-id="assigningPositionId"
            @reassign="onReassignChange"
            @assign="onAssignTargetChange"
            @open-order="openOrderDetail"
          />
        </template>
      </Column>
      <Column :header="t('production.lots.detail.steps.plannedStart')" style="width: 8rem">
        <template #body="{ data }">
          <template
            v-for="position in [positionForStep(data as LotStepResponse)]"
            :key="position?.id ?? 'none'"
          >
            <DeliveryDateCell
              :info="plannedInfoFor(position)"
              info-key="startDate"
              :edit-target="!readonly ? plannedEditTarget(data as LotStepResponse, position) : null"
              @edit="openSetPlannedDate"
            />
          </template>
        </template>
      </Column>
      <Column :header="t('production.lots.detail.steps.plannedDate')" style="min-width: 11rem">
        <template #body="{ data }">
          <template
            v-for="position in [positionForStep(data as LotStepResponse)]"
            :key="position?.id ?? 'none'"
          >
            <DeliveryDateCell
              :info="plannedInfoFor(position)"
              info-key="date"
              :edit-target="!readonly ? plannedEditTarget(data as LotStepResponse, position) : null"
              @edit="openSetPlannedDate"
            />
          </template>
        </template>
      </Column>
      <Column :header="t('production.lots.detail.steps.setupMinutes')" style="width: 9rem">
        <template #body="{ data }">
          <InputNumber
            :model-value="(data as LotStepResponse).estimated_setup_minutes"
            :min="0"
            :disabled="readonly"
            fluid
            @update:model-value="
              (v) =>
                onFieldChange(data as LotStepResponse, {
                  estimated_setup_minutes: v as number | null,
                })
            "
          />
        </template>
      </Column>
      <Column :header="t('production.lots.detail.steps.perPieceMinutes')" style="width: 9rem">
        <template #body="{ data }">
          <InputNumber
            :model-value="(data as LotStepResponse).estimated_minutes_per_piece"
            :min="0"
            :min-fraction-digits="0"
            :max-fraction-digits="2"
            :disabled="readonly"
            fluid
            @update:model-value="
              (v) =>
                onFieldChange(data as LotStepResponse, {
                  estimated_minutes_per_piece: v as number | null,
                })
            "
          />
        </template>
      </Column>
      <Column :header="t('production.lots.detail.steps.note')" style="min-width: 10rem">
        <template #body="{ data }">
          <InputText
            :model-value="(data as LotStepResponse).note ?? ''"
            :disabled="readonly"
            fluid
            @update:model-value="
              (v) => onFieldChange(data as LotStepResponse, { note: (v as string) || null })
            "
          />
        </template>
      </Column>
      <Column v-if="!readonly" header-style="width: 3rem">
        <template #body="{ data }">
          <template
            v-for="position in [positionForStep(data as LotStepResponse)]"
            :key="position?.id ?? 'none'"
          >
            <template
              v-for="completable in [completableOrder(position)]"
              :key="completable?.id ?? 'none'"
            >
              <span
                v-if="completable"
                v-tooltip.top="
                  canCompletePosition(position) ? undefined : missing(Permission.WRITE_INSPECTIONS)
                "
              >
                <Button
                  icon="mdi mdi-check-circle-outline"
                  size="small"
                  severity="success"
                  text
                  rounded
                  :disabled="!canCompletePosition(position)"
                  v-tooltip.top.focus="t('production.lots.detail.steps.complete')"
                  :aria-label="t('production.lots.detail.steps.complete')"
                  data-testid="lot-step-complete"
                  @click="completable && openCompletion(completable, position)"
                />
              </span>
            </template>
          </template>
        </template>
      </Column>
      <Column v-if="!readonly" header-style="width: 3rem">
        <template #body="{ data }">
          <span
            v-tooltip.top="
              !isPositionUnassigned(data as LotStepResponse)
                ? t('production.lots.detail.steps.assignedFieldLockedTooltip')
                : undefined
            "
          >
            <Button
              icon="mdi mdi-delete-outline"
              size="small"
              severity="danger"
              text
              rounded
              :disabled="!isPositionUnassigned(data as LotStepResponse)"
              :aria-label="t('production.lots.detail.steps.remove')"
              @click="removeStep(data as LotStepResponse)"
            />
          </span>
        </template>
      </Column>

      <template #empty>
        <EmptyState :message="t('production.lots.detail.steps.empty')" />
      </template>
    </DataTable>
    </div>

    <ContextMenu ref="cm" :model="contextMenuItems" @hide="contextMenuItem = null" />

    <SetPlannedDateDialog
      v-model:visible="showSetPlannedDate"
      :target="plannedDateEditTarget"
      @saved="onPlannedDateSaved"
    />
    <ProductionOrderCompletionDialog
      v-model:visible="showCompletion"
      :order="completionTarget"
      :steps="completionSteps"
      @recorded="onCompletionRecorded"
    />
    <OrderCreateForm
      v-model:visible="showCreateOrder"
      :preset-supplier-id="createOrderPresetSupplierId"
      @created="onOrderCreated"
    />
    <OrderDetailDialog
      v-if="orderDetailOrderId !== null"
      v-model:visible="showOrderDetail"
      :order-id="orderDetailOrderId"
    />
  </div>
</template>

<style scoped lang="scss">
.step-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.step-list-header {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.step-list-title {
  font-size: var(--font-size-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--p-text-muted-color);
}

.step-list-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

// Same tint as the global row hover in main.scss, applied to every row of
// the hovered position (see onTableMouseOver).
.step-table :deep(tr.position-row-hovered > td) {
  background: color-mix(in srgb, var(--p-primary-color) 10%, transparent) !important;
}
</style>
