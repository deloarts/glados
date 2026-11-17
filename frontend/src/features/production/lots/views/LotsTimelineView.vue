<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useProductionLotsStore } from '../../stores/productionLotsStore'
import { useProductionLotsFiltersStore } from '../stores/productionLotsFiltersStore'
import { getLot } from '../../api/getLot'
import { getProductionOrder } from '../api/getProductionOrder'
import { buildLotGanttTasks } from '../utils/lotsGanttTasks'
import { useMadeItemLabel } from '@/features/made-items'
import type { LotWithSchedule, ResolvedPositionSchedule } from '../utils/lotsGanttTasks'
import type { LotPositionResponse, LotResponse } from '../../types/productionLotsResponse'
import { toWallClockDate } from '@/core/utils/dates'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import AppGanttChart from '@/shared/components/gantt/AppGanttChart.vue'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { LiveResource } from '@/core/realtime/resources'
import type { IColumnConfig } from '@svar-ui/vue-gantt'

// Lots have no dates of their own, only steps do, resolved here from the
// production orders (internal/mixed positions) or purchase order delivery
// date (external positions) each step's position is linked to. That means
// one full lot detail fetch plus one production-order fetch per position,
// so the batch stays small compared to the orders timeline's limit.
const LOTS_TIMELINE_LIMIT = 50

const { t } = useI18n()
const { format: madeItemLabel } = useMadeItemLabel()
const lotsStore = useProductionLotsStore()
const filtersStore = useProductionLotsFiltersStore()

const loading = ref(false)
const lotsWithSchedule = ref<LotWithSchedule[]>([])

watchLoadingBar(loading)

function toDate(value: string | null): Date | null {
  return value ? toWallClockDate(value) : null
}

async function resolvePositionSchedule(
  position: LotPositionResponse,
): Promise<ResolvedPositionSchedule | null> {
  if (position.kind === 'external') {
    const date = toDate(position.expected_delivery_date ?? null)
    return date ? { positionId: position.id, start: date, end: date } : null
  }

  if ((position.production_orders ?? []).length === 0) return null

  const orders = await Promise.all(
    (position.production_orders ?? []).map((po) => getProductionOrder(po.id)),
  )

  let start: Date | null = null
  let end: Date | null = null
  for (const order of orders) {
    const orderStart = toDate(order.actual_start ?? order.planned_start)
    const orderEnd = toDate(order.actual_end ?? order.planned_end)
    if (orderStart && (!start || orderStart < start)) start = orderStart
    if (orderEnd && (!end || orderEnd > end)) end = orderEnd
  }

  return start && end ? { positionId: position.id, start, end } : null
}

async function resolveLotSchedule(lot: LotResponse): Promise<LotWithSchedule> {
  const resolved = await Promise.all((lot.positions ?? []).map(resolvePositionSchedule))
  const schedules = resolved.filter((s): s is ResolvedPositionSchedule => s !== null)
  return { lot, schedules }
}

async function fetchTimeline(): Promise<void> {
  loading.value = true
  try {
    await lotsStore.refresh({ limit: LOTS_TIMELINE_LIMIT })
    const relevant = lotsStore.items.filter((lot) => {
      if (filtersStore.hideCompleted && lot.status === 'completed') return false
      if (filtersStore.hideCanceled && lot.status === 'canceled') return false
      return true
    })
    const fullLots = await Promise.all(relevant.map((lot) => getLot(lot.id)))
    lotsWithSchedule.value = await Promise.all(fullLots.map(resolveLotSchedule))
  } finally {
    loading.value = false
  }
}

const tasks = computed(() => buildLotGanttTasks(lotsWithSchedule.value, madeItemLabel))

const columns = computed<IColumnConfig[]>(() => [
  {
    id: 'text',
    header: t('production.lots.timeline.columns.lotNumber'),
    width: 220,
    flexgrow: 1,
    sort: true,
  },
  {
    id: 'status',
    header: t('production.lots.timeline.columns.status'),
    width: 130,
    align: 'center',
    sort: true,
    getter: (obj) => (obj.status ? t(`production.lots.status.${obj.status}`) : ''),
  },
  {
    id: 'start',
    header: t('production.lots.timeline.columns.startDate'),
    width: 130,
    align: 'center',
    sort: true,
  },
  {
    id: 'duration',
    header: t('production.lots.timeline.columns.durationDays'),
    width: 130,
    align: 'center',
    sort: true,
  },
])

onMounted(fetchTimeline)
watch(() => lotsStore.refreshTrigger, fetchTimeline)
watch(() => [filtersStore.hideCompleted, filtersStore.hideCanceled], fetchTimeline)

useLiveRefresh([LiveResource.PRODUCTION_LOTS, LiveResource.PRODUCTION_ORDERS], fetchTimeline)
</script>

<template>
  <PageLayout>
    <div v-if="!loading && tasks.length === 0" class="empty-note">
      {{ t('production.lots.timeline.empty') }}
    </div>
    <AppGanttChart v-else class="gantt" :tasks="tasks" :columns="columns" :readonly="true" />
  </PageLayout>
</template>

<style scoped lang="scss">
.gantt {
  flex: 1;
  min-height: 0;
}

.empty-note {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
