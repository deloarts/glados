<script setup lang="ts">
import { computed, onMounted, reactive, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { hasAction } from '@/core/utils/lifecycleActions'
import { extractApiError } from '@/core/utils/errors'
import { API_MAX_PAGE_SIZE } from '@/core/constants/table'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { getProductionMachines } from '@/features/production-machines'
import { getMachinePools } from '@/features/production-machines'
import { useProductionLotDetailStore } from '../stores/productionLotDetailStore'
import { useProductionQueueStore } from '../../stores/productionQueueStore'
import { useMachineCapability } from '../../composables/useMachineCapability'
import { useLotPositionAssignmentHelpers } from '../composables/useLotPositionAssignmentHelpers'
import { stepMethodLabel } from '../../utils/lotStepDisplay'
import { HelpButton } from '@/shared/help'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'

import type { ProductionMachineResponse } from '@/features/production-machines'
import type { MachinePoolResponse } from '@/features/production-machines'
import type {
  LotPositionProductionOrderSummary,
  LotPositionResponse,
} from '../../types/productionLotsResponse'
import type { AssignInternalPositionOrderInput } from '../../types/productionLotsRequest'
import { bySequence } from '../../utils/sequence'
import EmptyState from '@/shared/components/EmptyState.vue'

defineOptions({ inheritAttrs: false })

const props = defineProps<{
  lotId: number
}>()

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const { toastOnError } = useErrorToast()
const detailStore = useProductionLotDetailStore()
const queueStore = useProductionQueueStore()
const {
  machineCoversPosition,
  poolCoversPosition,
  getCapableMachines,
  positionHasExternalMethods,
  candidatePoolsForPosition,
} = useMachineCapability()

// ── Machine / pool selection ────────────────────────────────────────────
// A machine and a pool are mutually exclusive; picking one clears the other.

const machines = ref<ProductionMachineResponse[]>([])
const loadingMachines = ref(false)
const selectedMachineId = ref<number | null>(null)

const pools = ref<MachinePoolResponse[]>([])
const loadingPools = ref(false)
const selectedPoolId = ref<number | null>(null)

const {
  sortedSteps,
  positionRequiresMachineAssignment,
  resolvedPoolFor,
  uncoveredMethodNames,
} = useLotPositionAssignmentHelpers(pools)

const selectedMachine = computed<ProductionMachineResponse | null>(
  () => machines.value.find((m) => m.id === selectedMachineId.value) ?? null,
)

const selectedPool = computed<MachinePoolResponse | null>(
  () => pools.value.find((p) => p.id === selectedPoolId.value) ?? null,
)

// Archived machines and pools stay selectable, sorted last.
const { sortedOptions: machineOptions, isArchived: isMachineArchived } =
  useArchivableOptions(machines)
const { sortedOptions: poolOptions, isArchived: isPoolArchived } = useArchivableOptions(pools)

// The same archived-last rule for plain arrays.
function sortArchivedLast<T extends { archived: boolean }>(items: T[]): T[] {
  const live: T[] = []
  const archived: T[] = []
  for (const item of items) (item.archived ? archived : live).push(item)
  return [...live, ...archived]
}

type AssignTarget = { kind: 'machine' | 'pool'; id: number } | null

const selectedTarget = computed<AssignTarget>(() => {
  if (selectedMachine.value) return { kind: 'machine', id: selectedMachine.value.id }
  if (selectedPool.value) return { kind: 'pool', id: selectedPool.value.id }
  return null
})

watch(selectedMachineId, (v) => {
  if (v !== null) selectedPoolId.value = null
})

watch(selectedPoolId, (v) => {
  if (v !== null) selectedMachineId.value = null
})

async function loadMachines(): Promise<void> {
  loadingMachines.value = true
  try {
    const result = await getProductionMachines({ limit: API_MAX_PAGE_SIZE, include_archived: true })
    machines.value = result.items
  } finally {
    loadingMachines.value = false
  }
}

async function loadPools(): Promise<void> {
  loadingPools.value = true
  try {
    const result = await getMachinePools({ limit: API_MAX_PAGE_SIZE, include_archived: true })
    pools.value = result.items
  } finally {
    loadingPools.value = false
  }
}

onMounted(() => {
  loadMachines().catch(toastOnError())
  loadPools().catch(toastOnError())
})

// ── Unassigned positions ─────────────────────────────────────────────

const unassignedPositions = computed<LotPositionResponse[]>(() =>
  [...(detailStore.lot?.positions ?? [])]
    .filter((p) => hasAction(p, 'assign_internal'))
    .sort(bySequence),
)

// ── Auto-pool flow ─────────────────────────────────────────────────────
// Without an explicit target each machine-requiring row resolves its own
// pool. Manual-only rows are assigned through "queue without machine".

type PositionWarning = 'incompatible' | 'external' | 'no-pool' | null

function positionWarning(position: LotPositionResponse): PositionWarning {
  if (selectedTarget.value) {
    if (selectedMachine.value && !machineCoversPosition(position, selectedMachine.value)) {
      return 'incompatible'
    }
    if (selectedPool.value && !poolCoversPosition(position, selectedPool.value)) {
      return 'incompatible'
    }
  } else if (positionRequiresMachineAssignment(position) && !resolvedPoolFor(position)) {
    return 'no-pool'
  }
  if (positionHasExternalMethods(position)) {
    return 'external'
  }
  return null
}

function warningTooltip(position: LotPositionResponse): string {
  const warning = positionWarning(position)
  if (warning === 'external') return t('production.lots.detail.manageProduction.externalMethodTooltip')
  if (warning === 'no-pool') {
    return t('production.lots.detail.manageProduction.noPoolTooltip', {
      methods: uncoveredMethodNames(position).join(' + '),
    })
  }
  return t('production.lots.detail.manageProduction.incompatibleTooltip')
}

function isDisabled(position: LotPositionResponse): boolean {
  if (assigningId.value !== null) return true
  if (selectedTarget.value) {
    // Only 'incompatible' blocks assignment. 'external' is a heads-up, the
    // position stays assignable.
    return positionWarning(position) === 'incompatible'
  }
  if (positionRequiresMachineAssignment(position)) {
    return positionWarning(position) === 'no-pool'
  }
  // Manual-only rows are assigned through the secondary action.
  return true
}

// ── Assign ───────────────────────────────────────────────────────────

const assigningId = ref<number | null>(null)
const errorMessage = ref<string | null>(null)

async function assign(position: LotPositionResponse): Promise<void> {
  if (isDisabled(position)) return
  if (selectedTarget.value) {
    await doAssign(position, selectedTarget.value)
    return
  }
  const pool = resolvedPoolFor(position)
  if (!pool) return
  await doAssign(position, { kind: 'pool', id: pool.id })
}

async function assignUnassigned(position: LotPositionResponse): Promise<void> {
  if (assigningId.value !== null || positionRequiresMachineAssignment(position)) return
  await doAssign(position, null)
}

async function doAssign(position: LotPositionResponse, target: AssignTarget): Promise<void> {
  assigningId.value = position.id
  errorMessage.value = null

  try {
    const orderInput: AssignInternalPositionOrderInput =
      target?.kind === 'pool'
        ? { machine_pool_id: target.id, quantity: position.quantity_remaining }
        : { machine_id: target?.id ?? null, quantity: position.quantity_remaining }

    await detailStore.assignInternal(props.lotId, position.id, {
      orders: [orderInput],
    })
  } catch (e) {
    errorMessage.value =
      extractApiError(e) ?? t('production.lots.detail.manageProduction.errors.unknown')
  } finally {
    assigningId.value = null
  }
}

// ── Needs a machine ────────────────────────────────────────────────────
// Internal positions with orders that still have no machine, read off the
// backend's no_machine_assigned conflict.

const needsMachinePositions = computed<LotPositionResponse[]>(() =>
  [...(detailStore.lot?.positions ?? [])]
    .filter(
      (p) =>
        (p.kind === 'internal' || p.kind === 'mixed') &&
        (p.production_orders ?? []).some((o) => (o.conflicts ?? []).includes('no_machine_assigned')),
    )
    .sort(bySequence),
)

function unassignedOrders(position: LotPositionResponse): LotPositionProductionOrderSummary[] {
  return (position.production_orders ?? []).filter((o) =>
    (o.conflicts ?? []).includes('no_machine_assigned'),
  )
}

function capableMachinesFor(position: LotPositionResponse): ProductionMachineResponse[] {
  return getCapableMachines(position, machines.value)
}

// Routing a machine-less order is an explicit pick per order, offering
// covering pools and capable machines.
interface TargetOption {
  key: string
  label: string
  archived: boolean
}

interface TargetGroup {
  key: 'pools' | 'machines'
  label: string
  items: TargetOption[]
}

function orderTargetGroupsFor(position: LotPositionResponse): TargetGroup[] {
  const groups: TargetGroup[] = []
  const candidatePools = sortArchivedLast(candidatePoolsForPosition(position, pools.value))
  if (candidatePools.length > 0) {
    groups.push({
      key: 'pools',
      label: t('production.lots.detail.manageProduction.poolsGroup'),
      items: candidatePools.map((p) => ({ key: `pool:${p.id}`, label: p.name, archived: p.archived })),
    })
  }
  const candidateMachines = sortArchivedLast(capableMachinesFor(position))
  if (candidateMachines.length > 0) {
    groups.push({
      key: 'machines',
      label: t('production.lots.detail.manageProduction.machinesGroup'),
      items: candidateMachines.map((m) => ({
        key: `machine:${m.id}`,
        label: m.internal_name,
        archived: m.archived,
      })),
    })
  }
  return groups
}

const orderTargetSelections = reactive<Record<number, string | null>>({})
const routingOrderId = ref<number | null>(null)

// Option keys are composite, so archived state is looked up per position.
function isOrderTargetArchived(position: LotPositionResponse, orderId: number): boolean {
  const key = orderTargetSelections[orderId]
  if (!key) return false
  const option = orderTargetGroupsFor(position)
    .flatMap((group) => group.items)
    .find((item) => item.key === key)
  return !!option?.archived
}

async function assignOrderMachine(orderId: number): Promise<void> {
  const key = orderTargetSelections[orderId] ?? null
  if (!key || routingOrderId.value !== null) return

  routingOrderId.value = orderId
  errorMessage.value = null

  try {
    const [kind, rawId] = key.split(':')
    const id = Number(rawId)
    await queueStore.reassignMachine(orderId, kind === 'pool' ? { machinePoolId: id } : id)
    await detailStore.refetch()
    delete orderTargetSelections[orderId]
  } catch (e) {
    errorMessage.value =
      extractApiError(e) ?? t('production.lots.detail.manageProduction.errors.unknown')
  } finally {
    routingOrderId.value = null
  }
}
</script>

<template>
  <Panel class="manage-production-panel fill-panel" v-bind="$attrs">
    <template #header>
      <div class="panel-header-row">
        <div class="panel-header-main">
          <span class="panel-title">{{ t('production.lots.detail.manageProduction.title') }}</span>
          <Tag
            v-if="unassignedPositions.length > 0"
            :value="
              t('production.lots.detail.manageProduction.unassignedCount', {
                count: unassignedPositions.length,
              })
            "
            severity="secondary"
          />
          <Tag
            v-if="needsMachinePositions.length > 0"
            :value="
              t('production.lots.detail.manageProduction.needsMachineCount', {
                count: needsMachinePositions.length,
              })
            "
            severity="warn"
          />
        </div>
        <HelpButton slug="production/manage-production" size="small" rounded />
      </div>
    </template>

    <!-- Machine / pool selector -->
    <div class="machine-section">
      <div class="target-selectors">
        <div class="target-selector">
          <label :id="`${uid}-select-machine-label`" :for="`${uid}-select-machine`" class="field-label">
            <i class="mdi mdi-robot-industrial-outline" aria-hidden="true" />
            {{ t('production.lots.detail.manageProduction.selectMachine') }}
          </label>
          <Select
            v-model="selectedMachineId"
            :input-id="`${uid}-select-machine`"
            :aria-labelledby="`${uid}-select-machine-label`"
            :options="machineOptions"
            option-label="internal_name"
            option-value="id"
            :loading="loadingMachines"
            :placeholder="t('production.lots.detail.assignInternal.selectMachine')"
            show-clear
            fluid
            size="small"
          >
            <template #option="{ option }">
              <span>{{ option.internal_name }}</span>
              <ArchivedOptionTag v-if="option.archived" />
            </template>
            <template #value>
              <span v-if="selectedMachine">{{ selectedMachine.internal_name }}</span>
              <ArchivedOptionTag v-if="selectedMachine?.archived" />
            </template>
          </Select>
          <ArchivedSelectionWarning v-if="isMachineArchived(selectedMachine)" />
        </div>
        <div class="target-selector">
          <label :id="`${uid}-select-pool-label`" :for="`${uid}-select-pool`" class="field-label">
            <i class="mdi mdi-view-grid-outline" aria-hidden="true" />
            {{ t('production.lots.detail.manageProduction.selectPool') }}
          </label>
          <Select
            v-model="selectedPoolId"
            :input-id="`${uid}-select-pool`"
            :aria-labelledby="`${uid}-select-pool-label`"
            :options="poolOptions"
            option-label="name"
            option-value="id"
            :loading="loadingPools"
            :placeholder="t('production.lots.detail.manageProduction.selectPoolPlaceholder')"
            show-clear
            fluid
            size="small"
          >
            <template #option="{ option }">
              <span>{{ option.name }}</span>
              <ArchivedOptionTag v-if="option.archived" />
            </template>
            <template #value>
              <span v-if="selectedPool">{{ selectedPool.name }}</span>
              <ArchivedOptionTag v-if="selectedPool?.archived" />
            </template>
          </Select>
          <ArchivedSelectionWarning v-if="isPoolArchived(selectedPool)" />
        </div>
      </div>
    </div>

    <!-- Without an explicit target the auto-flow resolves a pool per row. -->
    <Message
      v-if="!selectedTarget && unassignedPositions.some(positionRequiresMachineAssignment)"
      severity="warn"
      :closable="false"
      size="small"
    >
      {{ t('production.lots.detail.manageProduction.autoAssignBanner') }}
    </Message>

    <!-- Unassigned positions -->
    <div class="rows-section">
      <EmptyState v-if="unassignedPositions.length === 0" :message="t('production.lots.detail.manageProduction.noPositions')" icon="mdi mdi-robot-industrial-outline" />

      <div v-else class="rows-list">
        <div
          v-for="position in unassignedPositions"
          :key="position.id"
          class="row-card"
          :class="{
            'row-card--warning': ['incompatible', 'no-pool'].includes(
              positionWarning(position) ?? '',
            ),
            'row-card--external-note': positionWarning(position) === 'external',
          }"
        >
          <i
            v-if="positionWarning(position)"
            class="mdi mdi-alert warning-badge"
            :class="{ 'warning-badge--info': positionWarning(position) === 'external' }"
            aria-hidden="true"
            v-tooltip.left="warningTooltip(position)"
          />

          <div
            class="row-header"
            :class="{ 'row-header--disabled': isDisabled(position) }"
            role="button"
            tabindex="0"
            v-tooltip="
              !selectedTarget && !positionRequiresMachineAssignment(position)
                ? t('production.lots.detail.manageProduction.selectMachineFirst')
                : undefined
            "
            @click="assign(position)"
            @keydown.enter="assign(position)"
            @keydown.space.prevent="assign(position)"
          >
            <span class="row-seq">#{{ position.sequence }}</span>
            <div class="row-chips">
              <span v-for="step in sortedSteps(position)" :key="step.id" class="step-chip">
                <span class="step-chip-method">{{ stepMethodLabel(step) }}</span>
                <span class="step-chip-seq">#{{ step.sequence }}</span>
              </span>
            </div>
            <Tag
              v-if="
                !selectedTarget &&
                positionRequiresMachineAssignment(position) &&
                resolvedPoolFor(position)
              "
              :value="
                t('production.lots.detail.manageProduction.resolvedPool', {
                  pool: resolvedPoolFor(position)!.name,
                })
              "
              severity="info"
            />
            <span class="row-qty">{{ position.quantity_remaining }} / {{ position.quantity }}</span>
            <i
              v-if="assigningId === position.id"
              class="mdi mdi-loading mdi-spin row-chevron"
              aria-hidden="true"
            />
          </div>
          <div class="row-secondary">
            <Button
              :label="t('production.lots.detail.manageProduction.queueWithoutMachine')"
              icon="mdi mdi-progress-question"
              text
              size="small"
              :disabled="assigningId !== null || positionRequiresMachineAssignment(position)"
              v-tooltip.top="
                positionRequiresMachineAssignment(position)
                  ? t('production.lots.detail.manageProduction.queueWithoutMachineTooltip')
                  : undefined
              "
              @click.stop="assignUnassigned(position)"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Internal positions whose orders still have no machine. -->
    <div v-if="needsMachinePositions.length > 0" class="rows-section">
      <div class="field-label">
        {{ t('production.lots.detail.manageProduction.needsMachineTitle') }}
      </div>
      <div class="rows-list">
        <div v-for="position in needsMachinePositions" :key="position.id" class="row-card">
          <div class="row-header row-header--static">
            <span class="row-seq">#{{ position.sequence }}</span>
            <div class="row-chips">
              <span v-for="step in sortedSteps(position)" :key="step.id" class="step-chip">
                <span class="step-chip-method">{{ stepMethodLabel(step) }}</span>
                <span class="step-chip-seq">#{{ step.sequence }}</span>
              </span>
            </div>
          </div>

          <div v-for="order in unassignedOrders(position)" :key="order.id" class="order-route-row">
            <span :id="`${uid}-order-${order.id}`" class="order-route-number">{{ order.production_order_number }}</span>
            <span class="order-route-qty">{{ order.quantity }}</span>
            <div class="order-route-target">
              <Select
                v-model="orderTargetSelections[order.id]"
                :aria-labelledby="`${uid}-order-${order.id}`"
                :options="orderTargetGroupsFor(position)"
                option-label="label"
                option-value="key"
                option-group-label="label"
                option-group-children="items"
                :placeholder="t('production.lots.detail.manageProduction.selectTargetPlaceholder')"
                size="small"
                fluid
              >
                <template #option="{ option }">
                  <span>{{ option.label }}</span>
                  <ArchivedOptionTag v-if="option.archived" />
                </template>
              </Select>
              <ArchivedSelectionWarning v-if="isOrderTargetArchived(position, order.id)" />
            </div>
            <Button
              :label="t('production.lots.detail.manageProduction.assignMachine')"
              size="small"
              :loading="routingOrderId === order.id"
              :disabled="!orderTargetSelections[order.id] || routingOrderId !== null"
              @click="assignOrderMachine(order.id)"
            />
          </div>
        </div>
      </div>
    </div>

    <div v-if="errorMessage" class="panel-footer">
      <Message severity="error" :closable="false" size="small">
        {{ errorMessage }}
      </Message>
    </div>
  </Panel>
</template>

<style scoped lang="scss">
.manage-production-panel {
  flex: 0 0 auto;
  --fill-panel-gap: var(--space-3);
}

.panel-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: var(--space-2);
}

.panel-header-main {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.machine-section {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.target-selectors {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
}

.target-selector {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.target-selector .field-label {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.field-label {
  font-size: var(--font-size-sm);
  font-weight: 500;
}

.rows-section {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}



.rows-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.row-card {
  position: relative;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  display: flex;
  flex-direction: column;
}

.row-card--warning {
  border-color: var(--p-orange-500);
}

.row-card--external-note {
  border-color: var(--p-blue-500);
}

.warning-badge {
  position: absolute;
  top: 0.5rem;
  right: 0.625rem;
  color: var(--p-orange-500);
  font-size: var(--font-size-md);
  cursor: help;
}

.warning-badge--info {
  color: var(--p-blue-500);
}

.row-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-2);
  cursor: pointer;

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: -2px;
  }
}

.row-header--disabled {
  cursor: default;
  opacity: 0.6;
}

.row-header--static {
  cursor: default;
}

.order-route-row {
  display: grid;
  grid-template-columns: auto auto 1fr auto;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-2);
  border-top: 1px solid var(--p-content-border-color);
}

.order-route-number {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.order-route-qty {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
  white-space: nowrap;
}

.order-route-target {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.row-secondary {
  display: flex;
  justify-content: flex-end;
  padding: 0 var(--space-2) var(--space-1);
  border-top: 1px solid var(--p-content-border-color);
}

.row-seq {
  font-weight: 700;
  font-size: var(--font-size-sm);
}

.row-chips {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  padding-right: var(--space-4);
}

.step-chip {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  background: var(--p-surface-50);
}

.p-dark .step-chip {
  background: var(--p-surface-800);
}

.step-chip-method {
  font-size: var(--font-size-xs);
  font-weight: 600;
}

.step-chip-seq {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.row-qty {
  font-size: var(--font-size-sm);
  font-variant-numeric: tabular-nums;
  color: var(--p-text-muted-color);
  white-space: nowrap;
}

.row-chevron {
  color: var(--p-text-muted-color);
}

.panel-footer {
  flex-shrink: 0;
}
</style>
