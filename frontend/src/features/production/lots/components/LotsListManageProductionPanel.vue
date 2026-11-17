<script setup lang="ts">
import { computed, onMounted, reactive, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { hasAction } from '@/core/utils/lifecycleActions'
import { extractApiError } from '@/core/utils/errors'
import { API_MAX_PAGE_SIZE } from '@/core/constants/table'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { getProductionMachines } from '@/features/production-machines'
import { getMachinePools } from '@/features/production-machines'
import { assignInternalPosition } from '../api/assignInternalPosition'
import { reassignProductionOrderMachine } from '../../api/reassignProductionOrderMachine'
import { useProductionLotsStore } from '../../stores/productionLotsStore'
import { useProductionLotsSelectionStore } from '../stores/productionLotsSelectionStore'
import { useMachineCapability } from '../../composables/useMachineCapability'
import { useLotPositionAssignmentHelpers } from '../composables/useLotPositionAssignmentHelpers'
import { stepMethodLabel } from '../../utils/lotStepDisplay'
import { HelpButton } from '@/shared/help'

import type { ProductionMachineResponse } from '@/features/production-machines'
import type { MachinePoolResponse } from '@/features/production-machines'
import type { SelectedItem } from '../stores/productionLotsSelectionStore'
import type { LotPositionProductionOrderSummary } from '../../types/productionLotsResponse'
import type { AssignInternalPositionOrderInput } from '../../types/productionLotsRequest'
import EmptyState from '@/shared/components/EmptyState.vue'

defineOptions({ inheritAttrs: false })

const emit = defineEmits<{
  assigned: []
}>()

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const { toastOnError } = useErrorToast()
const lotsStore = useProductionLotsStore()
const selectionStore = useProductionLotsSelectionStore()
const { positionHasExternalMethods } = useMachineCapability()

const machines = ref<ProductionMachineResponse[]>([])
const loadingMachines = ref(false)

const pools = ref<MachinePoolResponse[]>([])
const loadingPools = ref(false)

const { sortedSteps, positionRequiresMachineAssignment, resolvedPoolFor, uncoveredMethodNames } =
  useLotPositionAssignmentHelpers(pools)

async function loadMachines(): Promise<void> {
  loadingMachines.value = true
  try {
    const result = await getProductionMachines({ limit: API_MAX_PAGE_SIZE })
    machines.value = result.items.filter((machine) => !machine.archived)
  } finally {
    loadingMachines.value = false
  }
}

async function loadPools(): Promise<void> {
  loadingPools.value = true
  try {
    const result = await getMachinePools({ limit: API_MAX_PAGE_SIZE })
    pools.value = result.items.filter((pool) => !pool.archived)
  } finally {
    loadingPools.value = false
  }
}

onMounted(() => {
  loadMachines().catch(toastOnError())
  loadPools().catch(toastOnError())
})

// Pools and machines share one Select keyed "pool:3" or "machine:7", so the
// setter keeps the two store fields mutually exclusive. Archived machines
// and pools are left out: the backend refuses to queue work on an archived
// machine, and Auto-Plan places nothing through an archived pool.
interface TargetOption {
  key: string
  label: string
}

interface TargetGroup {
  key: 'pools' | 'machines'
  label: string
  items: TargetOption[]
}

const targetGroups = computed<TargetGroup[]>(() => {
  const groups: TargetGroup[] = []
  if (pools.value.length > 0) {
    groups.push({
      key: 'pools',
      label: t('production.lots.detail.manageProduction.poolsGroup'),
      items: pools.value.map((p) => ({ key: `pool:${p.id}`, label: p.name })),
    })
  }
  if (machines.value.length > 0) {
    groups.push({
      key: 'machines',
      label: t('production.lots.detail.manageProduction.machinesGroup'),
      items: machines.value.map((m) => ({ key: `machine:${m.id}`, label: m.internal_name })),
    })
  }
  return groups
})

const selectedTargetKey = computed<string | null>({
  get: () => {
    if (selectionStore.selectedPool) return `pool:${selectionStore.selectedPool.id}`
    if (selectionStore.selectedMachine) return `machine:${selectionStore.selectedMachine.id}`
    return null
  },
  set: (key) => {
    if (!key) {
      selectionStore.selectedPool = null
      selectionStore.selectedMachine = null
      return
    }
    const [kind, rawId] = key.split(':')
    const id = Number(rawId)
    if (kind === 'pool') {
      selectionStore.selectedMachine = null
      selectionStore.selectedPool = pools.value.find((p) => p.id === id) ?? null
    } else {
      selectionStore.selectedPool = null
      selectionStore.selectedMachine = machines.value.find((m) => m.id === id) ?? null
    }
  },
})

// Option keys are composite, so the selection is looked up in the flat list.
const selectedTargetOption = computed<TargetOption | null>(() => {
  const key = selectedTargetKey.value
  if (!key) return null
  return targetGroups.value.flatMap((group) => group.items).find((item) => item.key === key) ?? null
})

// A new target invalidates rows checked against the previous one.
watch(
  () => [selectionStore.selectedMachine, selectionStore.selectedPool],
  () => selectionStore.clearItems(),
)

function unassignedOrders(item: SelectedItem): LotPositionProductionOrderSummary[] {
  return (item.position.production_orders ?? []).filter((o) =>
    (o.conflicts ?? []).includes('no_machine_assigned'),
  )
}

// A position that offers an internal assignment gets a fresh order, capped at
// the remaining quantity, unless it waits for a machine on a queued order,
// which the row then routes.
function isFreshAssignRow(item: SelectedItem): boolean {
  return hasAction(item.position, 'assign_internal') && unassignedOrders(item).length === 0
}

// ── Auto-pool flow ─────────────────────────────────────────────────
// Without an explicit target each machine-requiring fresh row resolves its
// own pool. Manual-only rows are unaffected.

const hasExplicitTarget = computed<boolean>(
  () => !!selectionStore.selectedMachine || !!selectionStore.selectedPool,
)

// Only a fresh machine-requiring row without explicit target depends on a
// covering pool.
function canSubmitRow(item: SelectedItem): boolean {
  if (hasExplicitTarget.value) return true
  if (!isFreshAssignRow(item)) return true
  if (!positionRequiresMachineAssignment(item.position)) return true
  return resolvedPoolFor(item.position) !== null
}

// ── Per-row quantity (fresh rows only) ─────────────────────────────

const rowQuantities = reactive<Record<string, number>>({})

function rowKey(item: SelectedItem): string {
  return `${item.lotId}:${item.position.id}`
}

watch(
  () => selectionStore.items,
  (items) => {
    const keys = new Set(items.map(rowKey))
    for (const key of Object.keys(rowQuantities)) {
      if (!keys.has(key)) delete rowQuantities[key]
    }
    for (const item of items) {
      const key = rowKey(item)
      if (rowQuantities[key] === undefined) rowQuantities[key] = item.position.quantity_remaining
    }
  },
  { immediate: true },
)

// ── Submit ───────────────────────────────────────────────────────────

const submitting = ref(false)
const errorMessage = ref<string | null>(null)

async function onSubmit(): Promise<void> {
  if (selectionStore.items.length === 0) return

  submitting.value = true
  errorMessage.value = null
  const failedLabels: string[] = []
  let anySucceeded = false

  for (const item of selectionStore.items) {
    // Stays in the list, disabled, until a pool covers it or a target is picked.
    if (!canSubmitRow(item)) continue

    try {
      if (isFreshAssignRow(item)) {
        const quantity = rowQuantities[rowKey(item)] ?? item.position.quantity_remaining
        const orderInput: AssignInternalPositionOrderInput = selectionStore.selectedPool
          ? { machine_pool_id: selectionStore.selectedPool.id, quantity }
          : selectionStore.selectedMachine
            ? { machine_id: selectionStore.selectedMachine.id, quantity }
            : positionRequiresMachineAssignment(item.position)
              ? { machine_pool_id: resolvedPoolFor(item.position)!.id, quantity }
              : { machine_id: null, quantity }

        await assignInternalPosition(item.lotId, item.position.id, {
          orders: [orderInput],
        })
      } else {
        const machine = selectionStore.selectedMachine
        const pool = selectionStore.selectedPool
        if (machine) {
          for (const order of unassignedOrders(item)) {
            await reassignProductionOrderMachine(order.id, { machine_id: machine.id })
          }
        } else if (pool) {
          for (const order of unassignedOrders(item)) {
            await reassignProductionOrderMachine(order.id, { machine_pool_id: pool.id })
          }
        }
      }
      selectionStore.removeItem(item.lotId, item.position.id)
      anySucceeded = true
    } catch (e) {
      failedLabels.push(`${item.lotNumber} #${item.position.sequence}`)
      errorMessage.value =
        extractApiError(e) ?? t('production.lots.detail.manageProduction.errors.unknown')
    }
  }

  submitting.value = false
  if (anySucceeded) lotsStore.triggerRefresh()
  if (failedLabels.length > 0) {
    errorMessage.value = t('production.lots.listManage.batchError', {
      items: failedLabels.join(', '),
    })
  } else {
    emit('assigned')
  }
}

function onClear(): void {
  selectionStore.clearSelection()
}
</script>

<template>
  <Panel class="manage-production-panel fill-panel" v-bind="$attrs">
    <template #header>
      <div class="panel-header-row">
        <div class="panel-header-main">
          <span class="panel-title">{{ t('production.lots.detail.manageProduction.title') }}</span>
          <Tag
            v-if="selectionStore.items.length > 0"
            :value="
              t('production.lots.listManage.selectedCount', { count: selectionStore.items.length })
            "
            severity="secondary"
          />
        </div>
        <HelpButton slug="production/manage-production" size="small" rounded />
      </div>
    </template>

    <div class="machine-section">
      <div class="target-selector">
        <label :id="`${uid}-select-target-label`" :for="`${uid}-select-target`" class="field-label">
          <i class="mdi mdi-robot-industrial-outline" aria-hidden="true" />
          {{ t('production.lots.detail.manageProduction.selectTarget') }}
        </label>
        <Select
          v-model="selectedTargetKey"
          :input-id="`${uid}-select-target`"
          :aria-labelledby="`${uid}-select-target-label`"
          :options="targetGroups"
          option-label="label"
          option-value="key"
          option-group-label="label"
          option-group-children="items"
          :loading="loadingMachines || loadingPools"
          :placeholder="t('production.lots.detail.manageProduction.selectTargetPlaceholder')"
          show-clear
          fluid
          size="small"
        >
          <template #optiongroup="{ option }">
            <Divider
              v-if="option.key === 'machines' && targetGroups.length > 1"
              class="group-divider"
            />
            <span class="group-label">
              <i
                :class="
                  option.key === 'pools'
                    ? 'mdi mdi-view-grid-outline'
                    : 'mdi mdi-robot-industrial-outline'
                "
                aria-hidden="true"
              />
              {{ option.label }}
            </span>
          </template>
          <template #option="{ option }">
            <span>{{ option.label }}</span>
          </template>
          <template #value>
            <span v-if="selectedTargetOption">{{ selectedTargetOption.label }}</span>
          </template>
        </Select>
      </div>
    </div>

    <EmptyState v-if="selectionStore.items.length === 0" :message="t('production.lots.listManage.selectStepPrompt')" icon="mdi mdi-cursor-default-click-outline" />

    <div v-else class="rows-section">
      <div class="rows-list">
        <div
          v-for="item in selectionStore.items"
          :key="rowKey(item)"
          class="row-card"
          :class="{ 'row-card--disabled': !canSubmitRow(item) }"
        >
          <div class="row-header row-header--static">
            <span class="row-seq">{{ item.lotNumber }} #{{ item.position.sequence }}</span>
            <i
              v-if="positionHasExternalMethods(item.position)"
              class="mdi mdi-alert external-note-icon"
              aria-hidden="true"
              v-tooltip.top="t('production.lots.detail.manageProduction.externalMethodTooltip')"
            />
            <i
              v-if="!canSubmitRow(item)"
              class="mdi mdi-alert-circle-outline no-pool-icon"
              aria-hidden="true"
              v-tooltip.top="
                t('production.lots.detail.manageProduction.noPoolTooltip', {
                  methods: uncoveredMethodNames(item.position).join(' + '),
                })
              "
            />
            <div class="row-chips">
              <span v-for="step in sortedSteps(item.position)" :key="step.id" class="step-chip">
                <span class="step-chip-method">{{ stepMethodLabel(step) }}</span>
              </span>
            </div>
            <Tag
              v-if="
                !hasExplicitTarget &&
                isFreshAssignRow(item) &&
                positionRequiresMachineAssignment(item.position) &&
                resolvedPoolFor(item.position)
              "
              :value="
                t('production.lots.detail.manageProduction.resolvedPool', {
                  pool: resolvedPoolFor(item.position)!.name,
                })
              "
              severity="info"
            />
            <Button
              icon="mdi mdi-close"
              severity="secondary"
              text
              rounded
              size="small"
              :aria-label="t('production.lots.listManage.removeFromSelection')"
              @click="selectionStore.removeItem(item.lotId, item.position.id)"
            />
          </div>

          <div v-if="isFreshAssignRow(item)" class="row-fields">
            <InputNumber
              v-model="rowQuantities[rowKey(item)]"
              :min="1"
              :max="item.position.quantity_remaining"
              :max-fraction-digits="0"
              :placeholder="t('production.lots.detail.assignInternal.quantity')"
              size="small"
            />
          </div>
          <div v-else class="order-route-rows">
            <div v-for="order in unassignedOrders(item)" :key="order.id" class="order-route-row">
              <span class="order-route-number">{{ order.production_order_number }}</span>
              <span class="order-route-qty">{{ order.quantity }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="panel-footer">
      <Message
        v-if="
          !hasExplicitTarget &&
          selectionStore.items.some(
            (item) => isFreshAssignRow(item) && positionRequiresMachineAssignment(item.position),
          )
        "
        severity="warn"
        :closable="false"
        size="small"
      >
        {{ t('production.lots.detail.manageProduction.autoAssignBanner') }}
      </Message>
      <Message
        v-if="errorMessage"
        severity="error"
        :closable="false"
        size="small"
        data-testid="manage-production-error"
      >
        {{ errorMessage }}
      </Message>
      <Button
        :label="t('production.lots.detail.manageProduction.assignMachine')"
        icon="mdi mdi-robot-industrial-outline"
        :disabled="selectionStore.items.length === 0"
        :loading="submitting"
        fluid
        @click="onSubmit"
      />
      <Button
        v-if="
          selectionStore.items.length > 0 ||
          selectionStore.selectedMachine ||
          selectionStore.selectedPool
        "
        :label="t('production.lots.listManage.clearSelection')"
        severity="secondary"
        outlined
        size="small"
        fluid
        @click="onClear"
      />
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

.group-divider {
  margin: 0 0 var(--space-2);
}

.group-label {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--p-text-muted-color);
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
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  display: flex;
  flex-direction: column;
}

.row-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-2);
}

.row-header--static {
  cursor: default;
}

.row-seq {
  font-weight: 700;
  font-size: var(--font-size-sm);
  white-space: nowrap;
}

.external-note-icon {
  color: var(--p-blue-500);
  font-size: var(--font-size-sm);
  cursor: help;
}

.no-pool-icon {
  color: var(--p-orange-500);
  font-size: var(--font-size-sm);
  cursor: help;
}

.row-card--disabled {
  opacity: 0.6;
}

.row-chips {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.step-chip {
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

.row-fields {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-2);
  padding: 0 var(--space-2) var(--space-2);
  border-top: 1px solid var(--p-content-border-color);
  padding-top: var(--space-2);
}

.order-route-rows {
  border-top: 1px solid var(--p-content-border-color);
}

.order-route-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-2);
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

.panel-footer {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
</style>
