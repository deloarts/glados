<script setup lang="ts">
// The docked, resizable positions surface of Manage mode: the optional
// Manage Orders and Manage Production panels and the position strip. It owns
// its toggle, resize drag and position dialogs. Each position button is
// offered when the position's actions offer it and the user holds the
// permission its endpoint needs.
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { formatDecimal } from '@/core/utils/numbers'
import { hasAction } from '@/core/utils/lifecycleActions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { InQuotationTag, useOpenQuoteRequestLinks } from '@/features/quote-requests'
import { useLotPositionActions } from '../../composables/useLotPositionActions'
import {
  lotPositionKindSeverity,
  lotPositionStatusKey,
  lotPositionStatusSeverityFor,
} from '../../../utils/lotStatus'
import LotManageOrdersPanel from '../LotManageOrdersPanel.vue'
import LotManageQuotesPanel from '../LotManageQuotesPanel.vue'
import LotManageProductionPanel from '../LotManageProductionPanel.vue'
import LotPositionAssignDialog from '../LotPositionAssignDialog.vue'
import LotPositionAssignInternalDialog from '../LotPositionAssignInternalDialog.vue'
import LotPositionProvisionDialog from '../LotPositionProvisionDialog.vue'
import LotAppendPositionDialog from './LotAppendPositionDialog.vue'

import type { LotResponse } from '../../../types/productionLotsResponse'
import { sortedBySequence } from '../../../utils/sequence'
import { useResizablePanelWidth } from '@/shared/composables/useResizablePanelWidth'
import PanelResizeHandle from '@/shared/components/layout/PanelResizeHandle.vue'

const props = defineProps<{
  lotId: number
  lot: LotResponse
  canWriteOrders: boolean
}>()

const { t } = useI18n()
const { hasPermission } = usePermissions()

// Unassigning, provisions and new positions change the lot; internal
// assignment creates production orders.
const canWriteLots = computed(() => hasPermission(Permission.WRITE_LOTS))

const sortedPositions = computed(() =>
  sortedBySequence(props.lot.positions),
)

// The open quote requests asking suppliers for the lot's positions.
const { lotPositions: quoteLinks } = useOpenQuoteRequestLinks(() => ({
  lotPositionIds: props.lot.positions.map((p) => p.id),
}))

const {
  assignTarget,
  showAssign,
  openAssign,
  assignInternalTarget,
  showAssignInternal,
  openAssignInternal,
  provisionsTarget,
  showProvisions,
  openProvisions,
  showAppendPosition,
  openAppendPosition,
  unassign,
} = useLotPositionActions(computed(() => props.lotId))

// At most one of the three panels is open; opening one closes the others.
const showManageOrders = ref(false)
const showManageQuotes = ref(false)
const showManageProduction = ref(false)

function showOnly(open: 'orders' | 'quotes' | 'production' | null): void {
  showManageOrders.value = open === 'orders'
  showManageQuotes.value = open === 'quotes'
  showManageProduction.value = open === 'production'
}

function toggleManageOrders(): void {
  showOnly(showManageOrders.value ? null : 'orders')
}

function toggleManageQuotes(): void {
  showOnly(showManageQuotes.value ? null : 'quotes')
}

function toggleManageProduction(): void {
  showOnly(showManageProduction.value ? null : 'production')
}

const { missing } = useMissingPermission()
const ordersBlocked = computed(() => missing(Permission.WRITE_ORDERS))
// The tooltips of the position buttons, '' when the user may take the action.
const assignInternalBlocked = computed(() => missing(Permission.WRITE_PRODUCTION_ORDERS))
const lotsBlocked = computed(() => missing(Permission.WRITE_LOTS))
const isAnyPanelOpen = computed(
  () =>
    (props.canWriteOrders && (showManageOrders.value || showManageQuotes.value)) ||
    (assignInternalBlocked.value === '' && showManageProduction.value),
)

// Clamped so the panel can never outgrow the dialog it is docked in.
const {
  width: panelWidth,
  isResizing,
  min: panelMin,
  max: panelMax,
  onResizeStart,
  onResizeKey,
} = useResizablePanelWidth({ defaultWidth: 360, min: 220, max: 520 })
</script>

<template>
  <div class="positions-dock" :class="{ 'is-resizing-ew': isResizing }">
    <LotManageOrdersPanel
      v-if="canWriteOrders && showManageOrders"
      :lot-id="lotId"
      :style="{ width: panelWidth + 'px' }"
    />
    <LotManageQuotesPanel
      v-if="canWriteOrders && showManageQuotes"
      :lot-id="lotId"
      :style="{ width: panelWidth + 'px' }"
    />
    <LotManageProductionPanel
      v-if="assignInternalBlocked === '' && showManageProduction"
      :lot-id="lotId"
      :style="{ width: panelWidth + 'px' }"
    />
    <PanelResizeHandle v-if="isAnyPanelOpen" :width="panelWidth" :min="panelMin" :max="panelMax" @start="onResizeStart" @key="onResizeKey" />

    <div class="positions-section">
      <div class="positions-header">
        <span class="positions-title">{{ t('production.lots.detail.positions.title') }}</span>
        <div class="positions-actions compact-buttons">
          <!-- Without the permission the buttons stay visible and say why. -->
          <span v-tooltip.top="ordersBlocked || undefined">
            <Button
              :label="t('production.lots.detail.manageOrders.toggle')"
              icon="mdi mdi-truck-outline"
              size="small"
              severity="secondary"
              :outlined="!showManageOrders"
              :disabled="!canWriteOrders"
              @click="toggleManageOrders"
            />
          </span>
          <span v-tooltip.top="ordersBlocked || undefined">
            <Button
              :label="t('production.lots.detail.manageQuotes.toggle')"
              icon="mdi mdi-scale-balance"
              size="small"
              severity="secondary"
              :outlined="!showManageQuotes"
              :disabled="!canWriteOrders"
              data-testid="manage-quotes"
              @click="toggleManageQuotes"
            />
          </span>
          <span v-tooltip.top="assignInternalBlocked || undefined">
            <Button
              :label="t('production.lots.detail.manageProduction.toggle')"
              icon="mdi mdi-robot-industrial-outline"
              size="small"
              severity="secondary"
              :outlined="!showManageProduction"
              :disabled="assignInternalBlocked !== ''"
              data-testid="manage-production"
              @click="toggleManageProduction"
            />
          </span>
          <span v-tooltip.top="lotsBlocked || undefined">
            <Button
              :label="t('production.lots.detail.positions.append')"
              icon="mdi mdi-plus"
              size="small"
              severity="secondary"
              outlined
              :disabled="!canWriteLots || !hasAction(lot, 'edit_structure')"
              data-testid="append-position"
              @click="openAppendPosition"
            />
          </span>
        </div>
      </div>

      <div class="position-cards">
        <div v-for="position in sortedPositions" :key="position.id" class="position-card">
          <div class="position-card-header">
            <span class="position-seq">#{{ position.sequence }}</span>
            <Tag
              :value="t(`production.lots.positionKind.${position.kind}`)"
              :severity="lotPositionKindSeverity[position.kind]"
            />
            <Tag
              :value="
                t(`production.lots.positionStatus.${lotPositionStatusKey(position.status, position.kind)}`)
              "
              :severity="lotPositionStatusSeverityFor(position.status, position.kind)"
            />
            <InQuotationTag :requests="quoteLinks[position.id]" />
            <span class="position-progress">{{ position.quantity_completed }} / {{ position.quantity }}</span>
          </div>

          <div
            v-if="position.kind === 'external' || position.kind === 'mixed'"
            class="position-order-info"
          >
            <span v-if="position.order_number">
              {{ t('production.lots.detail.positions.order') }}:
              {{ position.order_number }} ({{ position.supplier_name }})
              <!-- Once nothing is left open the rest hint below is gone, so the
                   newest line says itself that it was closed short. -->
              <Tag
                v-if="position.order_item_closed_short && position.quantity_remaining <= 0"
                :value="t('production.lots.detail.positions.closedShort')"
                severity="secondary"
                data-testid="closed-short-tag"
              />
            </span>
            <span v-if="position.expected_delivery_date">
              {{ t('production.lots.detail.positions.expectedDelivery') }}:
              {{ position.expected_delivery_date }}
            </span>
            <span
              v-if="position.order_item_closed_short && position.quantity_remaining > 0"
              data-testid="closed-short-rest"
            >
              {{
                t('production.lots.detail.positions.closedShortRest', {
                  quantity: position.quantity_remaining,
                })
              }}
            </span>
            <!-- The earlier lines of the position, each closed short, below the newest. -->
            <span
              v-for="line in position.earlier_order_lines"
              :key="line.order_item_id"
              class="earlier-line"
              data-testid="earlier-order-line"
            >
              {{ t('production.lots.detail.positions.order') }}:
              {{ line.order_number }} ({{ line.supplier_name }}),
              {{ formatDecimal(line.quantity) }} {{ line.unit }}
              <Tag
                v-if="line.closed_short"
                :value="t('production.lots.detail.positions.closedShort')"
                severity="secondary"
              />
            </span>
          </div>

          <div
            v-if="position.kind === 'internal' || position.kind === 'mixed'"
            class="position-order-info"
            data-testid="production-orders"
          >
            <div
              v-for="order in position.production_orders"
              :key="order.id"
              class="machine-order"
            >
              <span v-if="order.machine_id" class="machine-order-name">{{
                order.machine_internal_name || getEmptyPlaceholder()
              }}</span>
              <span
                v-else-if="order.machine_pool_id"
                class="machine-order-name machine-pool-label"
                v-tooltip.top="t('production.lots.detail.steps.pooledUnresolvedTooltip')"
              >
                <i class="mdi mdi-view-grid-outline" aria-hidden="true" />
                {{ order.machine_pool_name }}
              </span>
              <span v-else class="machine-order-name text-muted">{{ getEmptyPlaceholder() }}</span>
              <Tag :value="t(`production.lots.orderStatus.${order.status}`)" severity="secondary" />
              <span class="machine-order-progress">{{ order.quantity_completed }} / {{ order.quantity }}</span>
            </div>
          </div>

          <!-- Each span carries the tooltip, since a disabled button shows
               none of its own. -->
          <div class="position-card-actions">
            <span
              v-if="hasAction(position, 'assign_external')"
              v-tooltip.top="ordersBlocked || undefined"
            >
              <Button
                :label="t('production.lots.detail.positions.assign')"
                icon="mdi mdi-truck-outline"
                size="small"
                :disabled="ordersBlocked !== ''"
                data-testid="assign-external"
                @click="openAssign(position)"
              />
            </span>
            <span
              v-if="hasAction(position, 'assign_internal')"
              v-tooltip.top="assignInternalBlocked || undefined"
            >
              <Button
                :label="t('production.lots.detail.assignInternal.action')"
                icon="mdi mdi-robot-industrial-outline"
                size="small"
                severity="secondary"
                outlined
                :disabled="assignInternalBlocked !== ''"
                data-testid="assign-internal"
                @click="openAssignInternal(position)"
              />
            </span>
            <span
              v-if="hasAction(position, 'unassign_external')"
              v-tooltip.top="lotsBlocked || undefined"
            >
              <Button
                :label="t('production.lots.detail.positions.unassign')"
                icon="mdi mdi-truck-remove-outline"
                size="small"
                severity="secondary"
                outlined
                :disabled="lotsBlocked !== ''"
                data-testid="unassign-external"
                @click="unassign(position)"
              />
            </span>
            <span
              v-if="hasAction(position, 'record_provision')"
              v-tooltip.top="lotsBlocked || undefined"
            >
              <Button
                :disabled="lotsBlocked !== ''"
                data-testid="record-provision"
                :label="t('production.lots.detail.provisions.action')"
                icon="mdi mdi-truck-fast-outline"
                size="small"
                severity="secondary"
                outlined
                @click="openProvisions(position)"
              />
            </span>
          </div>
        </div>

        <div v-if="sortedPositions.length === 0" class="positions-empty">
          {{ t('production.lots.detail.positions.empty') }}
        </div>
      </div>
    </div>

    <LotPositionAssignDialog v-model:visible="showAssign" :lot-id="lotId" :position="assignTarget" />

    <LotPositionAssignInternalDialog
      v-model:visible="showAssignInternal"
      :lot-id="lotId"
      :position="assignInternalTarget"
    />

    <LotPositionProvisionDialog
      v-model:visible="showProvisions"
      :lot-id="lotId"
      :position="provisionsTarget"
    />

    <LotAppendPositionDialog v-model:visible="showAppendPosition" :lot-id="lotId" />
  </div>
</template>

<style scoped lang="scss">
.positions-dock {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  gap: var(--space-1);

  &.is-resizing-ew {
    user-select: none;
    cursor: ew-resize;
  }
}

.positions-section {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.positions-header {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.positions-title {
  font-size: var(--font-size-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--p-text-muted-color);
}

.positions-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.position-cards {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.position-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.position-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.position-seq {
  font-weight: 700;
}

.position-progress {
  margin-left: auto;
  font-variant-numeric: tabular-nums;
  color: var(--p-text-muted-color);
}

.position-order-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.earlier-line {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-1);
}

.machine-order {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.machine-order-name {
  font-weight: 600;
}

.machine-pool-label {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-style: italic;
  color: var(--p-text-muted-color);
}

.machine-order-progress {
  margin-left: auto;
  font-variant-numeric: tabular-nums;
}

.position-card-actions {
  display: flex;
  gap: var(--space-2);
}

.positions-empty {
  padding: var(--space-3) 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
