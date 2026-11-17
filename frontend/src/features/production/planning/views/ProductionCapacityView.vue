<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import {
  addDays,
  formatISODate,
  getISOWeek,
  startOfWeek,
  toDateKey,
  todayStart as tenantTodayStart,
  weekdayName,
} from '@/core/utils/dates'
import { getScheduleBoard } from '../api/getScheduleBoard'
import { useProductionLotsStore } from '../../stores/productionLotsStore'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import SectionCard from '@/shared/components/resource-view/SectionCard.vue'
import ProductionCapacityControls from '../components/ProductionCapacityControls.vue'
import MachineOrdersDialog from '../components/MachineOrdersDialog.vue'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { LiveResource } from '@/core/realtime/resources'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { overbookedMinutes, utilizationClass } from '../../utils/capacityUtilization'
import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import EmptyState from '@/shared/components/EmptyState.vue'

import type {
  MachineCapacityDayResponse,
  ScheduleBoardOrderResponse,
  ScheduleBoardResponse,
} from '../../types/scheduleBoardResponse'

const { t } = useI18n()
const { toastOnError } = useErrorToast()
const { formatNumber, formatDateTime } = useLocaleFormat()

const lotsStore = useProductionLotsStore()

const dateRange = ref<[Date, Date]>([
  startOfWeek(tenantTodayStart()),
  addDays(startOfWeek(tenantTodayStart()), 30),
])

const loading = ref(false)
watchLoadingBar(loading)
const board = ref<ScheduleBoardResponse>({
  machines: [],
  pools: [],
  unassigned: [],
  stale_since: null,
})

// The board walks on every read; the stored dates other pages show may lag
// behind until the background walk catches up.
const staleSince = computed(() =>
  board.value.stale_since ? formatDateTime(new Date(board.value.stale_since)) : null,
)
const ordersDialogVisible = ref(false)
const ordersDialogName = ref('')
const ordersDialogOrders = ref<ScheduleBoardOrderResponse[]>([])

const days = computed<Date[]>(() => {
  const [from, to] = dateRange.value
  if (!from || !to) return []
  const result: Date[] = []
  let cur = new Date(from)
  while (cur <= to) {
    result.push(cur)
    cur = addDays(cur, 1)
  }
  return result
})

interface CapacityRow {
  key: string
  // Pool rows are a rollup, not a bookable resource.
  kind: 'machine' | 'pool' | 'unassigned'
  machineId: number | null
  name: string
  capacityByDate: Map<string, MachineCapacityDayResponse>
  orders: ScheduleBoardOrderResponse[]
}

// Machines and pools sit in separate tables, since pools only roll up the
// machines above and are not resources of their own.
const machineRows = computed<CapacityRow[]>(() => {
  const machineTableRows: CapacityRow[] = (board.value.machines ?? []).map((machine) => ({
    key: `machine-${machine.machine_id}`,
    kind: 'machine',
    machineId: machine.machine_id,
    name: machine.machine_internal_name,
    capacityByDate: new Map((machine.capacity ?? []).map((day) => [day.date, day])),
    orders: machine.orders ?? [],
  }))

  const unassignedRow: CapacityRow = {
    key: 'unassigned',
    kind: 'unassigned',
    machineId: null,
    name: t('productionPlanning.noAssignment'),
    capacityByDate: new Map(),
    orders: board.value.unassigned ?? [],
  }

  return [...machineTableRows, unassignedRow]
})

const poolRows = computed<CapacityRow[]>(() =>
  (board.value.pools ?? []).map((pool) => ({
    key: `pool-${pool.pool_id}`,
    kind: 'pool',
    machineId: null,
    name: pool.pool_name,
    capacityByDate: new Map((pool.capacity ?? []).map((day) => [day.date, day])),
    orders: pool.orders ?? [],
  })),
)

// Lets the dialog show a floating order's trial machine as reserved.
const machineNamesById = computed<Record<number, string>>(() => {
  const names: Record<number, string> = {}
  for (const machine of board.value.machines ?? []) {
    names[machine.machine_id] = machine.machine_internal_name
  }
  return names
})

function formatHours(minutes: number): string {
  const hours = formatNumber(minutes / 60, { minimumFractionDigits: 1, maximumFractionDigits: 1 })
  return `${hours}h`
}

function dayHeaderDate(d: Date): string {
  return formatISODate(toDateKey(d))
}

function overbookedTooltip(day: MachineCapacityDayResponse | undefined): string | undefined {
  const minutes = overbookedMinutes(day)
  if (minutes <= 0) return undefined
  return t('productionSchedule.overbookedTooltip', { hours: formatHours(minutes) })
}

const todayStart = computed<Date>(() => tenantTodayStart())

function isPastDay(d: Date): boolean {
  return d < todayStart.value
}

function isToday(d: Date): boolean {
  return d.getTime() === todayStart.value.getTime()
}

// Column takes headerClass and bodyClass as plain strings, so an object
// would render as "[object Object]".
function todayColumnClass(d: Date): string | undefined {
  return isToday(d) ? 'today-column' : undefined
}

const zeroDays = computed<Set<string>>(() => {
  const set = new Set<string>()
  for (const day of days.value) {
    const dateStr = toDateKey(day)
    let sawCapacity = false
    let allZero = true
    for (const row of machineRows.value) {
      if (row.kind !== 'machine') continue
      const cap = row.capacityByDate.get(dateStr)
      if (cap) {
        sawCapacity = true
        if (cap.available_minutes !== 0) {
          allZero = false
          break
        }
      }
    }
    if (sawCapacity && allZero) set.add(dateStr)
  }
  return set
})

function isZeroDay(d: Date): boolean {
  return zeroDays.value.has(toDateKey(d))
}

function isMutedDay(d: Date): boolean {
  return isPastDay(d) || isZeroDay(d)
}

async function load(): Promise<void> {
  const [from, to] = dateRange.value
  if (!from || !to) return
  loading.value = true
  try {
    board.value = await getScheduleBoard({
      date_from: toDateKey(from),
      date_to: toDateKey(to),
    })
  } finally {
    loading.value = false
  }
}

watch(dateRange, load)
onMounted(load)

useLiveRefresh(
  [
    LiveResource.PRODUCTION_MACHINES,
    LiveResource.MACHINE_POOLS,
    LiveResource.PRODUCTION_ORDERS,
    LiveResource.PRODUCTION_LOTS,
  ],
  load,
)

function openOrders(row: CapacityRow): void {
  ordersDialogName.value = row.name
  ordersDialogOrders.value = row.orders
  ordersDialogVisible.value = true
}

function onAutoPlanApplied(): void {
  load().catch(toastOnError())
  lotsStore.triggerRefresh()
}
</script>

<template>
  <PageLayout :card="false">
    <template #controls>
      <ProductionCapacityControls v-model:date-range="dateRange" @applied="onAutoPlanApplied" />
    </template>

    <div class="cards-column">
      <Message v-if="staleSince" severity="info" :closable="false">
        {{ t('productionSchedule.staleSince', { time: staleSince }) }}
      </Message>
      <SectionCard :title="t('productionSchedule.machinesSectionTitle')" flush fill>
        <DataTable :value="machineRows" data-key="key" scrollable scroll-height="flex" size="small">
          <Column
            field="name"
            :header="t('productionSchedule.columns.machine')"
            style="min-width: 10rem"
            frozen
          />
          <Column :header="t('productionSchedule.columns.orders')" style="width: 8rem" frozen>
            <template #body="{ data }">
              <Button
                :label="String((data as CapacityRow).orders.length)"
                icon="mdi mdi-format-list-bulleted"
                size="small"
                text
                :disabled="(data as CapacityRow).orders.length === 0"
                @click="openOrders(data as CapacityRow)"
              />
            </template>
          </Column>
          <Column
            v-for="day in days"
            :key="toDateKey(day)"
            style="min-width: 7rem"
            :header-class="todayColumnClass(day)"
            :body-class="todayColumnClass(day)"
          >
            <template #header>
              <div class="day-header" :class="{ 'day-header-muted': isMutedDay(day) }">
                <div class="day-header-meta">
                  <span>{{ weekdayName(day) }}</span>
                  <span>{{ t('productionSchedule.weekPrefix') }}{{ getISOWeek(day) }}</span>
                </div>
                <div class="day-header-date">{{ dayHeaderDate(day) }}</div>
              </div>
            </template>
            <template #body="{ data }">
              <div class="day-cell" :class="{ 'day-cell-muted': isMutedDay(day) }">
                <div
                  v-if="(data as CapacityRow).kind !== 'unassigned'"
                  class="capacity-cell"
                  :class="
                    utilizationClass((data as CapacityRow).capacityByDate.get(toDateKey(day)))
                  "
                  v-tooltip.top="
                    overbookedTooltip((data as CapacityRow).capacityByDate.get(toDateKey(day)))
                  "
                >
                  <template v-if="(data as CapacityRow).capacityByDate.get(toDateKey(day))">
                    {{
                      formatHours(
                        (data as CapacityRow).capacityByDate.get(toDateKey(day))!.booked_minutes,
                      )
                    }}
                    /
                    {{
                      formatHours(
                        (data as CapacityRow).capacityByDate.get(toDateKey(day))!
                          .available_minutes,
                      )
                    }}
                  </template>
                  <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
                </div>
                <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
              </div>
            </template>
          </Column>

          <template #empty>
            <EmptyState :message="t('productionSchedule.empty')" />
          </template>
        </DataTable>
      </SectionCard>

      <SectionCard :title="t('productionSchedule.poolsSectionTitle')" flush fill>
        <DataTable :value="poolRows" data-key="key" scrollable scroll-height="flex" size="small">
          <Column
            field="name"
            :header="t('productionSchedule.columns.machine')"
            style="min-width: 10rem"
            frozen
          >
            <template #body="{ data }">
              <span class="row-name">
                <i class="mdi mdi-view-grid-outline" aria-hidden="true" />
                {{ (data as CapacityRow).name }}
              </span>
            </template>
          </Column>
          <Column :header="t('productionSchedule.columns.orders')" style="width: 8rem" frozen>
            <template #body="{ data }">
              <Button
                :label="String((data as CapacityRow).orders.length)"
                icon="mdi mdi-format-list-bulleted"
                size="small"
                text
                :disabled="(data as CapacityRow).orders.length === 0"
                @click="openOrders(data as CapacityRow)"
              />
            </template>
          </Column>
          <Column
            v-for="day in days"
            :key="toDateKey(day)"
            style="min-width: 7rem"
            :header-class="todayColumnClass(day)"
            :body-class="todayColumnClass(day)"
          >
            <template #header>
              <div class="day-header" :class="{ 'day-header-muted': isMutedDay(day) }">
                <div class="day-header-meta">
                  <span>{{ weekdayName(day) }}</span>
                  <span>{{ t('productionSchedule.weekPrefix') }}{{ getISOWeek(day) }}</span>
                </div>
                <div class="day-header-date">{{ dayHeaderDate(day) }}</div>
              </div>
            </template>
            <template #body="{ data }">
              <div class="day-cell" :class="{ 'day-cell-muted': isMutedDay(day) }">
                <div
                  class="capacity-cell"
                  :class="
                    utilizationClass((data as CapacityRow).capacityByDate.get(toDateKey(day)))
                  "
                  v-tooltip.top="
                    overbookedTooltip((data as CapacityRow).capacityByDate.get(toDateKey(day)))
                  "
                >
                  <template v-if="(data as CapacityRow).capacityByDate.get(toDateKey(day))">
                    {{
                      formatHours(
                        (data as CapacityRow).capacityByDate.get(toDateKey(day))!.booked_minutes,
                      )
                    }}
                    /
                    {{
                      formatHours(
                        (data as CapacityRow).capacityByDate.get(toDateKey(day))!
                          .available_minutes,
                      )
                    }}
                  </template>
                  <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
                </div>
              </div>
            </template>
          </Column>

          <template #empty>
            <EmptyState :message="t('productionSchedule.poolsEmpty')" />
          </template>
        </DataTable>
      </SectionCard>
    </div>
  </PageLayout>

  <MachineOrdersDialog
    v-model:visible="ordersDialogVisible"
    :machine-name="ordersDialogName"
    :orders="ordersDialogOrders"
    :machine-names-by-id="machineNamesById"
  />
</template>

<style scoped lang="scss">
.cards-column {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.row-name {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}

.day-header {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-weight: var(--p-datatable-column-title-font-weight);
}

.day-header-meta {
  display: flex;
  gap: var(--space-2);
}

.day-header-muted {
  color: var(--p-text-muted-color);
}

.day-cell {
  border-radius: 4px;
}

.day-cell-muted {
  background-color: var(--p-content-hover-background);
  color: var(--p-text-muted-color);
}

.capacity-cell {
  padding: var(--space-1) var(--space-1);
  border-radius: 4px;
}

.utilization-normal {
  background-color: color-mix(in srgb, var(--p-green-500) 15%, transparent);
}

.utilization-high {
  background-color: color-mix(in srgb, var(--p-orange-500) 20%, transparent);
}

.utilization-over {
  background-color: color-mix(in srgb, var(--p-red-500) 20%, transparent);
}

:deep(.today-column) {
  border-left: 1px solid var(--p-primary-500);
  border-right: 1px solid var(--p-primary-500);
}

:deep(th.today-column) {
  background-color: color-mix(in srgb, var(--p-primary-500) 15%, transparent);
}
</style>
