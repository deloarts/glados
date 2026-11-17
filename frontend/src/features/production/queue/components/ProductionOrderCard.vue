<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { MenuItem } from 'openvue/menuitem'

import { hasAction } from '@/core/utils/lifecycleActions'
import { useAppToast } from '@/core/composables/useAppToast'
import {
  isProductionOrderLocked,
  productionOrderPrioritySeverity,
  productionOrderStatusSeverity,
} from '../../utils/productionOrderStatus'
import {
  conflictLabelKey,
  conflictSeverity,
  conflictTooltipKey,
} from '../../utils/productionOrderConflicts'
import { useSourceMaterialCache } from '../composables/useSourceMaterialCache'
import { useProductionOrderCancel } from '../composables/useProductionOrderCancel'
import { useLotDetail } from '@/shared/composables/useLotDetail'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { formatISODate, formatPlanned } from '@/core/utils/dates'
import { extractApiError } from '@/core/utils/errors'
import { usePrint } from '@/shared/print'
import { formatMinutesDuration } from '../../utils/lotStepDisplay'
import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'

import { MadeItemThumbnailCell } from '@/features/made-items'
import { useMadeItemLabel } from '@/features/made-items'
import type { ProductionOrderResponse, ScheduleConflict } from '../../types/productionOrdersResponse'
import type { LotResponse } from '../../types/productionLotsResponse'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

const props = withDefaults(
  defineProps<{
    order: ProductionOrderResponse
    canWrite: boolean
    canManage: boolean
    draggable?: boolean
    // null while the lot is not loaded.
    processMethod?: string | null
    lot?: LotResponse | null
    // Manual-work columns have no machine, so no_machine_assigned is noise.
    hideNoMachineConflict?: boolean
  }>(),
  { draggable: true, processMethod: null, lot: null, hideNoMachineConflict: false },
)

const emit = defineEmits<{
  start: [order: ProductionOrderResponse]
  pause: [order: ProductionOrderResponse]
  cancel: [order: ProductionOrderResponse]
  split: [order: ProductionOrderResponse]
  merge: [order: ProductionOrderResponse]
  complete: [order: ProductionOrderResponse]
  scrap: [order: ProductionOrderResponse]
  'toggle-pin': [order: ProductionOrderResponse]
}>()

const { t } = useI18n()
const toast = useAppToast()
const printService = usePrint()
const { resolve: resolveSourceItem } = useSourceMaterialCache()
const { openLotDetail } = useLotDetail()
const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()
const { cancelBlocked } = useProductionOrderCancel()
const { format: madeItemLabel } = useMadeItemLabel()
const { formatNumber } = useLocaleFormat()

// Printing stays available on finished orders, since reprinting a lost
// label is normal.
const canPrint = computed(() => hasPermission(Permission.PRINT_DOCUMENTS))

type OrderPrintClassifier = 'production_order_label' | 'production_order_docket'

const printing = ref<OrderPrintClassifier | null>(null)

async function onPrint(classifier: OrderPrintClassifier): Promise<void> {
  const i18nStem = classifier === 'production_order_label' ? 'printLabel' : 'printDocket'
  printing.value = classifier
  try {
    const [job] = await printService.print({
      root_type: 'production_order',
      root_id: props.order.id,
      items: [{ classifier }],
    })
    if (job?.status === 'sent') {
      toast.success(props.order.production_order_number, t(`productionQueue.card.${i18nStem}Sent`))
    } else {
      toast.error(
        props.order.production_order_number,
        job?.error_message ?? t(`productionQueue.card.${i18nStem}Failed`),
      )
    }
  } catch (e) {
    toast.error(
      props.order.production_order_number,
      extractApiError(e) ?? t(`productionQueue.card.${i18nStem}Failed`),
    )
  } finally {
    printing.value = null
  }
}

const locked = computed(() => isProductionOrderLocked(props.order))
// A completed or canceled order has no action bar; inside it, the order's
// actions decide what the card offers.
const isTerminal = computed(
  () => props.order.status === 'completed' || props.order.status === 'canceled',
)
const canSplit = computed(() => hasAction(props.order, 'split') && props.order.quantity > 1)
const canMerge = computed(() => hasAction(props.order, 'merge'))
// A pure-manual position never gets a machine. False until the lot loads.
const isManualPosition = computed(() => {
  const steps =
    props.lot?.positions?.find((p) => p.id === props.order.lot_position_id)?.steps ?? []
  return steps.length > 0 && steps.every((s) => !s.fabrication_method_requires_machine)
})
// Operating an inspection position also needs write:inspections, as the
// backend enforces.
const canOperateInspection = computed(() => {
  const steps =
    props.lot?.positions?.find((p) => p.id === props.order.lot_position_id)?.steps ?? []
  const hasInspectionStep = steps.some((s) => s.role === 'inspection')
  return !hasInspectionStep || hasPermission(Permission.WRITE_INSPECTIONS)
})
// A pool-assigned order can start, the start dialog picks the machine.
// Only an order with neither blocks, unless the position is manual.
const needsMachineOrPool = computed(
  () =>
    !isManualPosition.value &&
    props.order.machine_id === null &&
    props.order.machine_pool_id == null,
)

// The backend's verdict on whether Start would be accepted right now.
const startBlocked = computed(
  () => needsMachineOrPool.value || !canOperateInspection.value || !props.order.can_start,
)

// canWrite and canManage are write:production_orders and
// manage:production_orders. Without them the card's actions stay visible
// but disabled, naming the missing permission.
const writeBlocked = computed(() =>
  props.canWrite ? '' : missing(Permission.WRITE_PRODUCTION_ORDERS),
)
const manageBlocked = computed(() =>
  props.canManage ? '' : missing(Permission.MANAGE_PRODUCTION_ORDERS),
)
const completeBlocked = computed<string | undefined>(() => {
  if (writeBlocked.value) return writeBlocked.value
  if (!canOperateInspection.value) return t('productionQueue.card.inspectionPermissionTooltip')
  return undefined
})

// Most actionable message first.
const startBlockedTooltip = computed<string | undefined>(() => {
  if (writeBlocked.value) return writeBlocked.value
  if (needsMachineOrPool.value) return t('productionQueue.card.noMachineTooltip')
  if (!canOperateInspection.value) return t('productionQueue.card.inspectionPermissionTooltip')
  if (!props.order.can_start) return t('productionQueue.card.cannotStartTooltip')
  return undefined
})

const visibleConflicts = computed<ScheduleConflict[]>(() =>
  (props.order.conflicts ?? []).filter(
    (c) => !(props.hideNoMachineConflict && c === 'no_machine_assigned'),
  ),
)

const massDisplayValue = computed(() => {
  const mass = props.order.made_item_mass
  return mass === null
    ? null
    : formatNumber(mass / 1000, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
})

// Only resolvable when sourced from stock; cached across cards.
const sourceItem = computed(() => resolveSourceItem(props.lot?.source_item_id ?? null))

const materialMismatch = computed(() => {
  const expected = props.order.made_item_material
  const actual = sourceItem.value?.material
  if (!expected || !actual) return false
  return expected.trim().toLowerCase() !== actual.trim().toLowerCase()
})

const sourceOrderStateLabel = computed(() => {
  const lot = props.lot
  if (!lot || !lot.source_order_id) return null
  if (lot.source_delivery_date) {
    return t('productionQueue.card.sourceDelivered', {
      date: formatISODate(lot.source_delivery_date),
    })
  }
  if (lot.source_expected_delivery_date) {
    return t('productionQueue.card.sourceExpected', {
      date: formatISODate(lot.source_expected_delivery_date),
    })
  }
  return t('productionQueue.card.sourceOrdered', { number: lot.source_order_number })
})

const moreMenu = ref()
const moreMenuItems = computed<MenuItem[]>(() => {
  const items: MenuItem[] = []
  if (canSplit.value) {
    items.push({
      label: t('productionQueue.card.actions.split'),
      icon: 'mdi mdi-call-split',
      command: () => emit('split', props.order),
    })
  }
  if (canMerge.value) {
    items.push({
      label: t('productionQueue.card.actions.merge'),
      icon: 'mdi mdi-call-merge',
      command: () => emit('merge', props.order),
    })
  }
  if (items.length > 0) items.push({ separator: true })
  if (hasAction(props.order, 'scrap')) {
    items.push({
      label: t('productionQueue.card.actions.scrap'),
      icon: 'mdi mdi-delete-alert-outline',
      command: () => emit('scrap', props.order),
    })
  }
  if (hasAction(props.order, 'cancel')) {
    // A menu item carries no tooltip, so its title names what blocks it.
    const blocked = cancelBlocked(props.order)
    items.push({
      label: t('productionQueue.card.actions.cancel'),
      icon: 'mdi mdi-close',
      disabled: blocked !== '',
      title: blocked || undefined,
      command: () => emit('cancel', props.order),
    })
  }
  return items
})

function toggleMoreMenu(event: Event): void {
  moreMenu.value?.toggle(event)
}
</script>


<template>
  <div class="order-card" :class="{ locked }">
    <div class="order-card-header">
      <span
        v-if="draggable && !locked"
        class="drag-handle"
        v-tooltip.top="t('productionQueue.card.dragHint')"
      >
        <i class="mdi mdi-drag-vertical" aria-hidden="true" />
      </span>
      <span
        v-else-if="draggable && locked"
        class="drag-handle-locked"
        v-tooltip.top="
          order.pinned
            ? t('productionQueue.card.lockedPinned')
            : t('productionQueue.card.lockedInProgress')
        "
      >
        <i class="mdi mdi-lock-outline" aria-hidden="true" />
      </span>
      <span v-else class="drag-handle-spacer" />
      <span class="order-headline">
        {{ madeItemLabel(order.made_item_part_number, order.made_item_revision) }}
        <span v-if="order.lot_position_count > 1" class="position-suffix"
          >· Pos {{ order.lot_position_sequence }}/{{ order.lot_position_count }}</span
        >
      </span>
      <Button
        icon="mdi mdi-tag-outline"
        text
        rounded
        size="small"
        severity="secondary"
        :disabled="!canPrint || printing === 'production_order_label'"
        :aria-label="t('productionQueue.card.printLabel')"
        v-tooltip.top="t('productionQueue.card.printLabel')"
        @click="onPrint('production_order_label')"
      />
      <Button
        icon="mdi mdi-file-document-outline"
        text
        rounded
        size="small"
        severity="secondary"
        :disabled="!canPrint || printing === 'production_order_docket'"
        :aria-label="t('productionQueue.card.printDocket')"
        v-tooltip.top="t('productionQueue.card.printDocket')"
        @click="onPrint('production_order_docket')"
      />
      <span v-tooltip.top="manageBlocked || undefined">
        <Button
          :icon="order.pinned ? 'mdi mdi-pin' : 'mdi mdi-pin-outline'"
          text
          rounded
          size="small"
          :severity="order.pinned ? 'warn' : 'secondary'"
          :disabled="!canManage"
          :aria-label="order.pinned ? t('productionQueue.card.unpin') : t('productionQueue.card.pin')"
          v-tooltip.top="
            order.pinned ? t('productionQueue.card.unpin') : t('productionQueue.card.pin')
          "
          data-testid="order-card-pin"
          @click="emit('toggle-pin', order)"
        />
      </span>
    </div>

    <span class="datum-value">
      <a
        class="lot-link"
        role="button"
        tabindex="0"
        @click.stop="openLotDetail(order.lot_id)"
        @keydown.enter.stop="openLotDetail(order.lot_id)"
      >
        {{ order.lot_number }}
      </a>
    </span>

    <div class="order-card-body">
      <div class="tags-row">
        <Tag
          :value="t(`productionQueue.status.${order.status}`)"
          :severity="productionOrderStatusSeverity[order.status]"
        />
        <Tag
          :value="t(`productionQueue.priority.${order.priority}`)"
          :severity="productionOrderPrioritySeverity[order.priority]"
        />
        <Tag
          v-if="order.waiting_on_raw_material"
          :value="t('productionQueue.card.waitingOnRawMaterial')"
          severity="warn"
          icon="mdi mdi-alert"
          v-tooltip.top="t('productionQueue.card.waitingOnRawMaterialTooltip')"
        />
        <Tag
          v-if="order.machine_pool_id"
          :value="t('productionQueue.card.poolTag', { pool: order.machine_pool_name })"
          severity="info"
          icon="mdi mdi-view-grid-outline"
          v-tooltip.top="
            order.machine_id === null
              ? t('productionQueue.card.poolUnresolvedTooltip')
              : t('productionQueue.card.poolResolvedTooltip')
          "
        />
        <Tag
          v-for="conflict in visibleConflicts"
          :key="conflict"
          :value="t(conflictLabelKey(conflict))"
          :severity="conflictSeverity[conflict]"
          icon="mdi mdi-alert"
          v-tooltip.top="t(conflictTooltipKey(conflict))"
        />
        <Tag
          v-if="materialMismatch"
          :value="t('productionQueue.card.materialMismatch')"
          severity="warn"
          icon="mdi mdi-alert"
          v-tooltip.top="
            t('productionQueue.card.materialMismatchTooltip', {
              expected: order.made_item_material,
              actual: sourceItem?.material,
            })
          "
        />
      </div>

      <div class="item-summary-row">
        <MadeItemThumbnailCell
          :item-id="order.made_item_id"
          :item-name="order.made_item_part_number"
          :size="'4.2rem'"
          no-image-icon="mdi mdi-image-outline"
          style="margin-right: var(--space-2)"
        />

        <div class="datum-grid">
          <span class="datum-label">{{ t('productionQueue.card.quantity') }}</span>
          <span class="datum-value">{{ order.quantity_completed }} / {{ order.quantity }}</span>

          <span class="datum-label">{{ t('productionQueue.card.processMethod') }}</span>
          <span class="datum-value">{{ processMethod ?? getEmptyPlaceholder() }}</span>

          <span class="datum-label">{{ t('production.lots.detail.record.execution.estimated') }}</span>
          <span class="datum-value">{{ formatMinutesDuration(order.estimated_duration_minutes) }}</span>

          <template v-if="order.planned_start">
            <span class="datum-label">{{ t('production.lots.detail.record.execution.planned') }}</span>
            <span class="datum-value"
              >{{ formatPlanned(order.planned_start) }} → {{ formatPlanned(order.planned_end) }}</span
            >
          </template>

          <span class="datum-label">{{ t('productionQueue.card.material') }}</span>
          <span class="datum-value">{{ order.made_item_material ?? getEmptyPlaceholder() }}</span>

          <span class="datum-label">{{ t('productionQueue.card.mass') }}</span>
          <span class="datum-value">{{
            massDisplayValue === null
              ? getEmptyPlaceholder()
              : t('productionQueue.card.massValue', { kg: massDisplayValue })
          }}</span>

          <span class="datum-label">{{ t('productionQueue.card.sourceMaterial') }}</span>
          <span class="datum-value source-material-value">
            <span>{{
              lot?.source_label || order.made_item_base_size || getEmptyPlaceholder()
            }}</span>
            <span v-if="lot?.source_sublabel" class="source-material-sublabel">{{
              lot.source_sublabel
            }}</span>
            <span v-if="sourceItem?.manufacturer_name" class="source-material-sublabel">{{
              sourceItem.manufacturer_name
            }}</span>
            <span v-if="sourceOrderStateLabel" class="source-material-sublabel">{{
              sourceOrderStateLabel
            }}</span>
          </span>
        </div>
      </div>

      <div v-if="order.note" class="note">{{ order.note }}</div>
    </div>

    <div v-if="!isTerminal" class="order-card-actions">
      <span v-if="order.status === 'queued'" v-tooltip.top="startBlockedTooltip">
        <Button
          :label="t('productionQueue.card.actions.start')"
          icon="mdi mdi-play"
          size="small"
          severity="success"
          :disabled="!canWrite || startBlocked"
          data-testid="order-card-start"
          @click="emit('start', order)"
        />
      </span>
      <span v-if="order.status === 'paused'" v-tooltip.top="startBlockedTooltip">
        <Button
          :label="t('productionQueue.card.actions.resume')"
          icon="mdi mdi-play-circle-outline"
          size="small"
          severity="success"
          :disabled="!canWrite || startBlocked"
          data-testid="order-card-resume"
          @click="emit('start', order)"
        />
      </span>
      <span v-if="hasAction(order, 'pause')" v-tooltip.top="writeBlocked || undefined">
        <Button
          :label="t('productionQueue.card.actions.pause')"
          icon="mdi mdi-pause"
          size="small"
          severity="warn"
          :disabled="!canWrite"
          data-testid="order-card-pause"
          @click="emit('pause', order)"
        />
      </span>
      <span v-if="hasAction(order, 'record_completion')" v-tooltip.top="completeBlocked">
        <Button
          :label="t('productionQueue.card.actions.complete')"
          icon="mdi mdi-check"
          size="small"
          severity="success"
          :disabled="!canWrite || !canOperateInspection"
          data-testid="order-card-complete"
          @click="emit('complete', order)"
        />
      </span>
      <span v-tooltip.top="writeBlocked || undefined">
        <Button
          icon="mdi mdi-dots-horizontal"
          size="small"
          severity="secondary"
          outlined
          :disabled="!canWrite"
          :aria-label="t('productionQueue.card.actions.more')"
          v-tooltip.top="t('productionQueue.card.actions.more')"
          data-testid="order-card-more"
          @click="toggleMoreMenu"
        />
      </span>
      <Menu ref="moreMenu" :model="moreMenuItems" popup />
    </div>
  </div>
</template>

<style scoped lang="scss">
.order-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  border-radius: var(--p-content-border-radius);
  border: 1px solid var(--p-content-border-color);
  background: var(--p-content-background);

  &.locked {
    background: var(--p-surface-100, var(--p-content-background));
  }
}

.order-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.drag-handle {
  display: inline-flex;
  align-items: center;
  cursor: grab;
  color: var(--p-text-muted-color);
}

.drag-handle-locked {
  display: inline-flex;
  align-items: center;
  cursor: not-allowed;
  color: var(--p-text-muted-color);
  opacity: 0.6;
}

.drag-handle-spacer {
  display: inline-flex;
  width: 1.2rem;
}

.order-headline {
  font-weight: 600;
  font-size: var(--font-size-md);
  flex: 1 1 auto;
}

.position-suffix {
  font-weight: 400;
  color: var(--p-text-muted-color);
}

.order-card-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.lot-link {
  color: var(--p-primary-color);
  text-decoration: none;
  width: fit-content;

  &:hover {
    text-decoration: underline;
  }
}

.lot-step {
  color: var(--p-text-muted-color);
}

.datum-grid {
  display: grid;
  grid-template-columns: 6rem auto;
  column-gap: var(--space-2);
  row-gap: var(--space-1);
  font-size: var(--font-size-sm);
}

.datum-label {
  color: var(--p-text-muted-color);
}

.datum-value {
  justify-self: start;
  min-width: 0;
}

.source-material-value {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.source-material-sublabel {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.item-summary-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding-top: var(--space-1);
  padding-bottom: var(--space-2);
}

.tags-row {
  display: flex;
  gap: var(--space-1);
  flex-wrap: wrap;
  padding-top: var(--space-1);
  padding-bottom: var(--space-3);
}

.note {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
  white-space: pre-wrap;
}

.order-card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}
</style>
