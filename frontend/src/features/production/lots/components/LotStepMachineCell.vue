<script setup lang="ts">
// Machine / Order cell of the lot step list. Shows the position's production
// order target (editable while the order is reassignable), offers the assign
// Select for an unassigned position, and links an external position's
// purchase order. Every pick is emitted; the parent decides whether it is
// written immediately or staged in a draft.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { useMachineCapability } from '../../composables/useMachineCapability'
import { buildAssignTargetGroups } from '../utils/lotStepAssignOptions'
import { reassignableOrder, targetKeyFor } from '../utils/lotStepPositionOrders'

import type { MachinePoolResponse, ProductionMachineResponse } from '@/features/production-machines'
import type { OrderResponse } from '@/features/orders'
import type { AssignTargetGroup } from '../utils/lotStepAssignOptions'
import type {
  PendingAssignments,
  PendingReassignments,
} from '../composables/useLotStructureDraft'
import type {
  LotPositionProductionOrderSummary,
  LotPositionResponse,
} from '../../types/productionLotsResponse'

const props = defineProps<{
  position: LotPositionResponse | undefined
  readonly: boolean
  staged?: boolean
  pendingAssignments?: PendingAssignments
  pendingReassignments?: PendingReassignments
  machines: ProductionMachineResponse[]
  pools: MachinePoolResponse[]
  orders: OrderResponse[]
  loadingTargets: boolean
  loadingOrders: boolean
  assigningOrderId: number | null
  assigningPositionId: number | null
}>()

const emit = defineEmits<{
  reassign: [order: LotPositionProductionOrderSummary, key: string | null]
  assign: [position: LotPositionResponse, key: string | null]
  openOrder: [orderId: number | null]
}>()

const { t } = useI18n()
const { hasPermission } = usePermissions()
const { getCapableMachines, candidatePoolsForPosition } = useMachineCapability()

// Same permissions the backend enforces on AssignInternalPosition and
// AssignExternalPosition; the reassign Select needs the internal one.
const canAssignInternal = computed(() => hasPermission(Permission.WRITE_PRODUCTION_ORDERS))
// Without write:production_orders the machine select stays visible while
// editing, disabled and naming the missing permission.
const { missing } = useMissingPermission()
const assignInternalBlocked = computed(() => missing(Permission.WRITE_PRODUCTION_ORDERS))
const canAssignExternal = computed(() => hasPermission(Permission.WRITE_ORDERS))
// Holding neither permission leaves an unassigned position's assign select
// visible but disabled, naming the first missing permission.
const assignBlocked = computed(() =>
  canAssignInternal.value || canAssignExternal.value
    ? ''
    : missing(Permission.WRITE_PRODUCTION_ORDERS, Permission.WRITE_ORDERS),
)

interface TargetGroup {
  key: 'pools' | 'machines'
  label: string
  items: { key: string; label: string }[]
}

// Pools and machines share one Select keyed "pool:<id>" / "machine:<id>",
// narrowed to the pools covering this position and the machines capable of it.
function targetGroupsFor(position: LotPositionResponse | undefined): TargetGroup[] {
  const groups: TargetGroup[] = []
  const poolOptions = candidatePoolsForPosition(position ?? null, props.pools)
  if (poolOptions.length > 0) {
    groups.push({
      key: 'pools',
      label: t('production.lots.detail.manageProduction.poolsGroup'),
      items: poolOptions.map((p) => ({ key: `pool:${p.id}`, label: p.name })),
    })
  }
  const machineOptions = getCapableMachines(position ?? null, props.machines)
  if (machineOptions.length > 0) {
    groups.push({
      key: 'machines',
      label: t('production.lots.detail.manageProduction.machinesGroup'),
      items: machineOptions.map((m) => ({ key: `machine:${m.id}`, label: m.internal_name })),
    })
  }
  return groups
}

// In staged mode a pending entry wins, even a null one, which means the
// draft clears the target.
function reassignModelValueFor(order: LotPositionProductionOrderSummary): string | null {
  if (!props.staged) return targetKeyFor(order)
  const pending = props.pendingReassignments ?? {}
  return order.id in pending ? pending[order.id]! : targetKeyFor(order)
}

function assignableFor(position: LotPositionResponse | undefined): position is LotPositionResponse {
  if (!position) return false
  if (position.kind !== 'unassigned' || props.readonly) return false
  // A draft-only position (negative id) exists only in staged mode, where
  // Save maps the pick onto the id the server hands back for it.
  return props.staged ? true : position.id > 0
}

function assignTargetGroupsFor(position: LotPositionResponse | undefined): AssignTargetGroup[] {
  if (!position) return []
  return buildAssignTargetGroups({
    position,
    machines: props.machines,
    pools: props.pools,
    orders: props.orders,
    canAssignInternal: canAssignInternal.value,
    canAssignExternal: canAssignExternal.value,
    labels: {
      pools: t('production.lots.detail.manageProduction.poolsGroup'),
      machines: t('production.lots.detail.manageProduction.machinesGroup'),
      manual: t('production.lots.detail.steps.manualGroup'),
      orders: t('production.lots.detail.steps.ordersGroup'),
      create: t('production.lots.detail.steps.createGroup'),
      queueWithoutMachine: t('production.lots.detail.steps.queueWithoutMachineOption'),
      createOrder: t('production.lots.detail.steps.createOrderOption'),
    },
  })
}
</script>

<template>
  <template v-for="order in [reassignableOrder(position)]" :key="order?.id ?? 'none'">
    <div
      v-if="order && !readonly"
      class="machine-cell"
      v-tooltip.top="assignInternalBlocked || undefined"
      data-testid="lot-step-machine-select"
    >
      <Select
        :aria-label="t('production.lots.detail.steps.machine')"
        :model-value="reassignModelValueFor(order)"
        :options="targetGroupsFor(position)"
        option-label="label"
        option-value="key"
        option-group-label="label"
        option-group-children="items"
        :loading="loadingTargets || assigningOrderId === order.id"
        :disabled="!canAssignInternal"
        :placeholder="t('production.lots.detail.manageProduction.selectTargetPlaceholder')"
        show-clear
        fluid
        @update:model-value="(v) => order && emit('reassign', order, (v as string) ?? null)"
      />
      <span v-if="order.machine_id && order.machine_pool_id" class="machine-pool-note">
        <i class="mdi mdi-view-grid-outline" aria-hidden="true" />
        {{ order.machine_pool_name }}
      </span>
    </div>
    <div v-else-if="order" class="machine-cell">
      <span v-if="order.machine_id">{{
        order.machine_internal_name || getEmptyPlaceholder()
      }}</span>
      <span
        v-else-if="order.machine_pool_id"
        class="machine-pool-label"
        v-tooltip.top="t('production.lots.detail.steps.pooledUnresolvedTooltip')"
      >
        <i class="mdi mdi-view-grid-outline" aria-hidden="true" />
        {{ order.machine_pool_name }}
      </span>
      <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      <span
        v-if="order.machine_id && order.machine_pool_id"
        class="machine-pool-note"
        >{{
          t('production.lots.detail.steps.resolvedFromPool', {
            pool: order.machine_pool_name,
          })
        }}</span
      >
    </div>
    <span
      v-else-if="position && (position.kind === 'internal' || position.kind === 'mixed')"
      class="text-muted"
      v-tooltip.top="t('production.lots.detail.steps.machineComplexTooltip')"
      >{{ t('production.lots.detail.steps.machineComplex') }}</span
    >
    <div
      v-else-if="
        assignableFor(position) && (assignTargetGroupsFor(position).length > 0 || assignBlocked)
      "
      class="machine-cell machine-cell--assign"
      v-tooltip.top="assignBlocked || undefined"
    >
      <Select
        :aria-label="t('production.lots.detail.steps.machine')"
        :model-value="staged ? (pendingAssignments?.[position.id] ?? null) : null"
        :options="assignTargetGroupsFor(position)"
        option-label="label"
        option-value="key"
        option-group-label="label"
        option-group-children="items"
        filter
        :show-clear="staged"
        :placeholder="t('production.lots.detail.steps.assignTargetPlaceholder')"
        :loading="loadingTargets || loadingOrders || (!staged && assigningPositionId === position.id)"
        :disabled="!!assignBlocked || (!staged && assigningPositionId === position.id)"
        fluid
        @update:model-value="(v) => position && emit('assign', position, (v as string) ?? null)"
      />
    </div>
    <span v-else-if="position?.kind !== 'external'" class="text-muted">{{
      getEmptyPlaceholder()
    }}</span>
  </template>
  <span
    v-if="position && (position.kind === 'external' || position.kind === 'mixed')"
    class="machine-order-link"
    role="button"
    tabindex="0"
    v-tooltip.top="t('production.lots.detail.steps.externalOrderTooltip')"
    @click="emit('openOrder', position.order_id ?? null)"
    @keydown.enter="emit('openOrder', position.order_id ?? null)"
    >{{ position.order_number }} · {{ position.supplier_name }}</span
  >
</template>

<style scoped lang="scss">
.machine-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.machine-pool-note {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-xs);
  font-style: italic;
  color: var(--p-text-muted-color);
}

.machine-pool-label {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-style: italic;
  color: var(--p-text-muted-color);
}

// Block, so for a mixed position it sits on its own line below the machine
// content instead of sharing one with the Select.
.machine-order-link {
  display: block;
  width: fit-content;
  cursor: pointer;
  color: var(--p-primary-color);
  font-size: var(--font-size-sm);

  &:hover {
    text-decoration: underline;
  }

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: 2px;
  }
}
</style>
