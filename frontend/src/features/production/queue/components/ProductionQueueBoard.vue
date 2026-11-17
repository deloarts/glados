<script setup lang="ts">
// Production queue board: one column per machine pool, machine and
// synthetic bucket, each split into active work, an Overdue group, one
// draggable group per day of the selected range and recent terminal orders.
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import draggable from 'vuedraggable'

import { useErrorToast } from '@/core/composables/useErrorToast'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { usePhoneLayout } from '@/core/composables/usePhoneLayout'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { LiveResource } from '@/core/realtime/resources'
import { HelpButton } from '@/shared/help'
import { useProductionQueueStore } from '../../stores/productionQueueStore'
import { useProductionSchedule } from '../../composables/useProductionSchedule'
import { isStaticColumn } from '../../utils/queueColumnRouting'
import { useQueueBoardColumns } from '../composables/useQueueBoardColumns'
import { useQueueBoardDateRange } from '../composables/useQueueBoardDateRange'
import { OVERDUE_KEY, useQueueBoardGroups } from '../composables/useQueueBoardGroups'
import { useQueueCardActions } from '../composables/useQueueCardActions'
import { useQueueHideNotReady } from '../composables/useQueueHideNotReady'
import ProductionOrderCard from './ProductionOrderCard.vue'
import ProductionQueueColumnHeader from './ProductionQueueColumnHeader.vue'
import ProductionOrderSplitDialog from './ProductionOrderSplitDialog.vue'
import ProductionOrderMergeDialog from './ProductionOrderMergeDialog.vue'
import ProductionOrderStartDialog from './ProductionOrderStartDialog.vue'
import ProductionOrderPauseDialog from './ProductionOrderPauseDialog.vue'
import ProductionOrderCompletionDialog from '../../components/ProductionOrderCompletionDialog.vue'
import ScrapPiecesDialog from '../../components/ScrapPiecesDialog.vue'
import ManufacturingAssessmentDialog from './ManufacturingAssessmentDialog.vue'

import type { MenuItem } from 'openvue/menuitem'
import type { ProductionOrderResponse } from '../../types/productionOrdersResponse'

const { t } = useI18n()
const { withErrorToast } = useErrorToast()
const store = useProductionQueueStore()

const {
  lotsById,
  orderedDateByPositionId,
  loading: scheduleLoading,
  complete: scheduleComplete,
} = useProductionSchedule()
watchLoadingBar(() => store.loading || store.refreshing || scheduleLoading.value)

const { boardColumns, positionFor, processMethodLabel, orderColumnKeyFor } =
  useQueueBoardColumns(lotsById)

const showCompleted = ref(false)
const { hideNotReady } = useQueueHideNotReady()
// A phone stacks the machines below each other, with no layout switch, and
// leaves rescheduling by drag to the desktop: on a touch screen a drag
// fights the scrolling.
const { phoneMode } = usePhoneLayout()
const boardMode = ref<'horizontal' | 'vertical'>(phoneMode.value ? 'vertical' : 'horizontal')

const modeLabel = computed(() =>
  boardMode.value === 'horizontal'
    ? t('productionQueue.board.modeHorizontal')
    : t('productionQueue.board.modeVertical'),
)

const modeMenuItems = computed<MenuItem[]>(() => [
  {
    label: t('productionQueue.board.modeHorizontal'),
    icon: 'mdi mdi-view-column',
    command: () => (boardMode.value = 'horizontal'),
  },
  {
    label: t('productionQueue.board.modeVertical'),
    icon: 'mdi mdi-view-stream',
    command: () => (boardMode.value = 'vertical'),
  },
])

function toggleMode(): void {
  boardMode.value = boardMode.value === 'horizontal' ? 'vertical' : 'horizontal'
}

const { todayStart, dateRange, rangeDays, dayKeys, boardDays, rollOverDay } =
  useQueueBoardDateRange()

const {
  localGroups,
  otherOrders,
  groupKey,
  isHidden,
  visibleCount,
  columnCount,
  rebuildLocalOrders,
  onDragStart,
  onDragEnd,
  checkMove,
  onGroupChange,
} = useQueueBoardGroups({
  todayStart,
  rangeDays,
  dayKeys,
  showCompleted,
  hideNotReady,
  lotsById,
  orderedDateByPositionId,
  orderColumnKeyFor,
})

const {
  canWrite,
  splitTarget,
  showSplit,
  mergeTarget,
  showMerge,
  startTarget,
  showStart,
  pauseTarget,
  showPause,
  completionTarget,
  showCompletion,
  completionSteps,
  assessmentTarget,
  showAssessment,
  scrapDialogRef,
  onCompletionRecorded,
  onPiecesScrapped,
  cardBindings,
} = useQueueCardActions({ lotsById, positionFor, processMethodLabel })

// The Overdue/day split is a calendar boundary, so a board left open over
// midnight is regrouped within five minutes even if nothing else changes.
const MIDNIGHT_CHECK_INTERVAL_MS = 5 * 60 * 1000
let midnightCheckInterval: ReturnType<typeof setInterval> | undefined

function onMidnightCheck(): void {
  if (rollOverDay()) rebuildLocalOrders()
}

// Gates the first-load skeleton only. A background re-sync patches the
// board in place instead of unmounting it.
const ready = ref(false)

// The orders arrive before their lots, which are fetched one by one, and a
// card without its lot sits in the wrong column with no method until they
// land. So the first load waits for the lots too, or for their fetch to end
// when one of them fails.
const boardShown = ref(false)
watch(
  () => ready.value && (scheduleComplete.value || !scheduleLoading.value),
  (settled) => {
    if (settled) boardShown.value = true
  },
)

onMounted(async () => {
  await withErrorToast(() => store.fetchAll(), { summary: t('productionQueue.board.loadError') })
  rebuildLocalOrders()
  ready.value = true
  midnightCheckInterval = setInterval(onMidnightCheck, MIDNIGHT_CHECK_INTERVAL_MS)
})

onUnmounted(() => {
  if (midnightCheckInterval) clearInterval(midnightCheckInterval)
})

// Split by resource so an order signal does not refetch machines too. A
// failed background re-sync is swallowed: the next signal retries it, and a
// toast per dropped packet would be noise on a shop-floor screen.
function refreshLive(resources: { machines?: boolean; pools?: boolean; orders?: boolean }): void {
  void store.refreshLive(resources).catch(() => {})
}

useLiveRefresh([LiveResource.PRODUCTION_MACHINES], () => refreshLive({ machines: true }))
useLiveRefresh([LiveResource.MACHINE_POOLS], () => refreshLive({ pools: true }))
useLiveRefresh([LiveResource.PRODUCTION_ORDERS, LiveResource.PRODUCTION_LOTS], () =>
  refreshLive({ orders: true }),
)
</script>

<template>
  <div class="queue-board">
    <Toolbar>
      <template #start>
        <DatePicker
          v-model="dateRange"
          selection-mode="range"
          show-button-bar
          :placeholder="t('productionQueue.board.dateRange')"
        />
        <Button
          :label="t('productionQueue.board.showCompleted')"
          icon="mdi mdi-check-circle-outline"
          severity="contrast"
          :text="!showCompleted"
          @click="showCompleted = !showCompleted"
        />
        <Button
          :label="t('productionQueue.board.hideNotReady')"
          icon="mdi mdi-timer-sand"
          severity="contrast"
          :text="!hideNotReady"
          v-tooltip.bottom="t('productionQueue.board.hideNotReadyTooltip')"
          data-testid="queue-hide-not-ready"
          @click="hideNotReady = !hideNotReady"
        />
        <SplitButton
          v-if="!phoneMode"
          :label="modeLabel"
          icon="mdi mdi-view-column"
          severity="contrast"
          text
          :model="modeMenuItems"
          @click="toggleMode"
        />
      </template>
      <!-- The queue is also the tab /production opens on, whose route path
           names no page, so the slug is spelled out. -->
      <template #end>
        <HelpButton slug="production/queue" rounded />
      </template>
    </Toolbar>

    <div v-if="!boardShown" class="board-loading">
      <ProgressSpinner style="width: 2rem; height: 2rem" stroke-width="6" />
    </div>

    <div v-else-if="store.machines.length === 0" class="board-empty">
      {{ t('productionQueue.board.empty') }}
    </div>

    <div
      v-else
      class="board-columns"
      :class="{ 'board-columns--vertical': boardMode === 'vertical' }"
    >
      <div
        v-for="machine in boardColumns"
        :key="machine.key"
        class="board-column"
        :class="{
          'board-column--unassigned':
            machine.kind !== 'machine' && machine.kind !== 'pool',
        }"
      >
        <ProductionQueueColumnHeader :column="machine" :count="columnCount(machine.key)" />

        <div class="column-list">
          <template v-if="(otherOrders[machine.key]?.active.length ?? 0) > 0">
            <div class="group-divider">
              {{ t('productionQueue.board.groups.active') }} ({{
                otherOrders[machine.key]!.active.length
              }})
            </div>
            <ProductionOrderCard
              v-for="order in otherOrders[machine.key]!.active"
              :key="order.id"
              v-bind="cardBindings(order, machine.kind, false)"
            />
          </template>

          <!-- Static columns (manual, inspection) use the same markup with
               dragging switched off. -->
          <template v-if="visibleCount(machine.key, OVERDUE_KEY) > 0">
            <div class="group-divider group-divider--overdue">
              {{ t('productionQueue.board.groups.overdue') }} ({{
                visibleCount(machine.key, OVERDUE_KEY)
              }})
            </div>
            <draggable
              v-model="localGroups[groupKey(machine.key, OVERDUE_KEY)]"
              item-key="id"
              class="column-list-draggable"
              handle=".drag-handle"
              :group="{ name: 'production-queue-overdue' }"
              :move="checkMove"
              :disabled="!canWrite || isStaticColumn(machine.kind) || phoneMode"
              ghost-class="order-card-ghost"
              @start="onDragStart"
              @end="onDragEnd"
              @change="onGroupChange(machine, $event)"
            >
              <template #item="{ element }">
                <ProductionOrderCard
                  v-show="!isHidden(element as ProductionOrderResponse)"
                  v-bind="
                    cardBindings(
                      element as ProductionOrderResponse,
                      machine.kind,
                      !isStaticColumn(machine.kind),
                    )
                  "
                />
              </template>
            </draggable>
          </template>

          <template v-for="day in boardDays" :key="day.key">
            <div class="group-divider" :class="{ 'group-divider--today': day.isToday }">
              {{ day.label }} ({{ visibleCount(machine.key, day.key) }})
            </div>
            <!-- Each day is its own Sortable group, so a card only moves
                 between columns within the same day and never reschedules. -->
            <draggable
              v-model="localGroups[groupKey(machine.key, day.key)]"
              item-key="id"
              class="column-list-draggable"
              handle=".drag-handle"
              :group="{ name: `production-queue-${day.key}` }"
              :move="checkMove"
              :disabled="!canWrite || isStaticColumn(machine.kind) || phoneMode"
              ghost-class="order-card-ghost"
              @start="onDragStart"
              @end="onDragEnd"
              @change="onGroupChange(machine, $event)"
            >
              <template #item="{ element }">
                <ProductionOrderCard
                  v-show="!isHidden(element as ProductionOrderResponse)"
                  v-bind="
                    cardBindings(
                      element as ProductionOrderResponse,
                      machine.kind,
                      !isStaticColumn(machine.kind),
                    )
                  "
                />
              </template>
            </draggable>
          </template>

          <div v-if="columnCount(machine.key) === 0" class="column-empty">
            {{ t('productionQueue.board.machineEmpty') }}
          </div>

          <template v-if="showCompleted && (otherOrders[machine.key]?.terminal.length ?? 0) > 0">
            <div class="group-divider">{{ t('productionQueue.board.groups.terminal') }}</div>
            <ProductionOrderCard
              v-for="order in otherOrders[machine.key]!.terminal"
              :key="order.id"
              v-bind="cardBindings(order, machine.kind, false)"
            />
          </template>
        </div>
      </div>
    </div>

    <ProductionOrderSplitDialog v-model:visible="showSplit" :order="splitTarget" />
    <ProductionOrderMergeDialog
      v-model:visible="showMerge"
      :order="mergeTarget"
      :orders="store.orders"
    />
    <ProductionOrderStartDialog v-model:visible="showStart" :order="startTarget" />
    <ProductionOrderPauseDialog v-model:visible="showPause" :order="pauseTarget" />
    <ProductionOrderCompletionDialog
      v-model:visible="showCompletion"
      :order="completionTarget"
      :steps="completionSteps"
      @recorded="onCompletionRecorded"
    />
    <ManufacturingAssessmentDialog v-model:visible="showAssessment" :order="assessmentTarget" />
    <ScrapPiecesDialog ref="scrapDialogRef" @scrapped="onPiecesScrapped" />
  </div>
</template>

<style scoped lang="scss">
.queue-board {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.board-loading,
.board-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1 1 auto;
  color: var(--p-text-muted-color);
}

.board-columns {
  display: flex;
  gap: var(--space-4);
  overflow-x: auto;
  flex: 1 1 auto;
  padding-bottom: var(--space-2);

  &.board-columns--vertical {
    flex-direction: column;
    overflow-x: hidden;
    overflow-y: auto;
  }
}

.board-columns--vertical .board-column {
  width: 100%;
  max-width: none;
}

.board-column {
  display: flex;
  flex-direction: column;
  min-width: 25rem;
  max-width: 25rem;
  background: var(--p-surface-50);
  border-radius: var(--p-content-border-radius);
  padding: var(--space-3);
  gap: var(--space-2);
}

.p-dark .board-column {
  background: var(--p-surface-900);
  border: 1px solid var(--p-content-border-color);
}

.board-column--unassigned {
  border: 1px dashed var(--p-content-border-color);
}

.column-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-height: 2rem;
  flex: 1 1 auto;
  overflow-y: auto;
}

.column-list-draggable {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.group-divider {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--p-text-muted-color);
  margin: var(--space-1) 0;

  &::after {
    content: '';
    flex: 1 1 auto;
    height: 1px;
    background: var(--p-content-border-color);
  }
}

.group-divider--overdue {
  color: var(--p-red-600);

  &::after {
    background: var(--p-red-200);
  }
}

// Today keeps its own accent so it stays findable once the range spans a
// week or more and every divider looks alike.
.group-divider--today {
  color: var(--p-primary-color);

  &::after {
    background: var(--p-primary-color);
    opacity: 0.4;
  }
}

.p-dark .group-divider--overdue {
  color: var(--p-red-400);

  &::after {
    background: var(--p-red-900);
  }
}

.column-empty {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
  text-align: center;
  padding: var(--space-4) 0;
}

:deep(.order-card-ghost) {
  opacity: 0.4;
}
</style>
