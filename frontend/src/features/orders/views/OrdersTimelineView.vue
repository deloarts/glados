<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import { useOrdersStore } from '../stores/ordersStore'
import { useOrdersFiltersStore } from '../stores/ordersFiltersStore'
import { buildOrderGanttTasks, filterOrdersForTimeline } from '../utils/ordersGanttTasks'
import AppGanttChart from '@/shared/components/gantt/AppGanttChart.vue'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { LiveResource } from '@/core/realtime/resources'
import type { IColumnConfig } from '@svar-ui/vue-gantt'

const TIMELINE_ORDERS_LIMIT = 200

const { t } = useI18n()
const ordersStore = useOrdersStore()
const filtersStore = useOrdersFiltersStore()

watchLoadingBar(() => ordersStore.loading)

const tasks = computed(() =>
  buildOrderGanttTasks(
    filterOrdersForTimeline(ordersStore.items, {
      hideDelivered: filtersStore.hideDelivered,
      hideCanceled: filtersStore.hideCanceled,
    }),
  ),
)

const columns = computed<IColumnConfig[]>(() => [
  {
    id: 'text',
    header: t('procurement.timeline.columns.orderNumber'),
    width: 220,
    flexgrow: 1,
    sort: true,
  },
  {
    id: 'status',
    header: t('procurement.timeline.columns.status'),
    width: 130,
    align: 'center',
    sort: true,
    getter: (obj) =>
      obj.kind === 'item'
        ? t(`orders.items.status.${obj.status}`)
        : t(`orders.status.${obj.status}`),
  },
  {
    id: 'start',
    header: t('procurement.timeline.columns.orderDate'),
    width: 130,
    align: 'center',
    sort: true,
  },
  {
    id: 'duration',
    header: t('procurement.timeline.columns.durationDays'),
    width: 130,
    align: 'center',
    sort: true,
  },
])

function fetchTimeline(): void {
  void ordersStore.refresh({ limit: TIMELINE_ORDERS_LIMIT })
}

onMounted(fetchTimeline)
watch(() => ordersStore.refreshTrigger, fetchTimeline)

useLiveRefresh([LiveResource.ORDERS], fetchTimeline)
</script>

<template>
  <PageLayout>
    <div v-if="!ordersStore.loading && tasks.length === 0" class="empty-note">
      {{ t('procurement.timeline.empty') }}
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
