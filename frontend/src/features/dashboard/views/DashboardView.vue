<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import DashboardHeader from '../components/DashboardHeader.vue'
import StatTile from '../components/StatTile.vue'
import ShopFloorPanel from '../components/ShopFloorPanel.vue'
import AlertsPanel from '../components/AlertsPanel.vue'
import WipProgressPanel from '../components/WipProgressPanel.vue'
import DemandPipelinePanel from '../components/DemandPipelinePanel.vue'
import SpendingPanel from '../components/SpendingPanel.vue'
import RecentItemsPanel from '../components/RecentItemsPanel.vue'
import TodoSummaryPanel from '../components/TodoSummaryPanel.vue'
import QuickLinksPanel from '../components/QuickLinksPanel.vue'
import { useDashboardSummary } from '../composables/useDashboardSummary'
import { useTodoTasks } from '@/features/todo'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useProductionPlanning } from '@/core/composables/useProductionPlanning'
import { useHostStore } from '@/core/host/stores/hostStore'

const { t } = useI18n()
const { productionPlanningEnabled } = useProductionPlanning()
const hostStore = useHostStore()
const router = useRouter()

const {
  productionQueueStore,
  madeDemandCounts,
  boughtDemandCounts,
  sourceDemandCounts,
  wipLots,
  overdueOrders,
  todayOrders,
  recentItems,
  loading,
  inProcessCount,
  overdueAndTodayCount,
  activeLotsCount,
  lotsCount,
  demandsCount,
  unreadCount,
  openDemandsCount,
  recentOrdersCount,
  spentRecentlyCents,
  dailySpendSeries,
} = useDashboardSummary()

const {
  overdue: todoOverdue,
  today: todoToday,
  dueNowCount: todoDueNowCount,
  loading: todoLoading,
} = useTodoTasks()

watchLoadingBar(loading)
watchLoadingBar(todoLoading)

// Every ring is backed by a real proportion in the data.
const totalActiveOrders = computed(
  () =>
    productionQueueStore.orders.filter((o) => o.status !== 'completed' && o.status !== 'canceled')
      .length,
)
</script>

<template>
  <div class="dashboard-view">
    <DashboardHeader class="dashboard-anim" style="--dashboard-anim-index: 0" />

    <div class="dashboard-kpi-row">
      <StatTile
        class="dashboard-anim"
        style="--dashboard-anim-index: 1"
        :label="t('dashboard.stats.inProcess')"
        :loading="loading"
        :value="inProcessCount"
        accent-var="var(--p-blue-500)"
        :ring="{
          max: totalActiveOrders,
          colorVar: 'var(--p-blue-500)',
          trackColorVar: 'var(--p-blue-100)',
        }"
        clickable
        @click="router.push('/production')"
      />
      <StatTile
        class="dashboard-anim"
        style="--dashboard-anim-index: 2"
        :label="t('dashboard.stats.overdueToday')"
        :loading="loading"
        :value="overdueAndTodayCount"
        accent-var="var(--p-orange-500)"
        :ring="{
          max: totalActiveOrders,
          colorVar: 'var(--p-orange-500)',
          trackColorVar: 'var(--p-orange-100)',
        }"
        clickable
        @click="router.push('/production')"
      />
      <StatTile
        class="dashboard-anim"
        style="--dashboard-anim-index: 3"
        :label="t('dashboard.stats.activeLots')"
        :loading="loading"
        :value="activeLotsCount"
        accent-var="var(--p-green-500)"
        :ring="{
          max: lotsCount,
          colorVar: 'var(--p-green-500)',
          trackColorVar: 'var(--p-green-100)',
        }"
        clickable
        @click="router.push('/production/lots')"
      />
      <StatTile
        class="dashboard-anim"
        style="--dashboard-anim-index: 4"
        :label="t('dashboard.stats.unreadNotifications')"
        :loading="loading"
        :value="unreadCount"
        icon="mdi mdi-bell-ring-outline"
        accent-var="var(--p-red-500)"
      />
      <StatTile
        class="dashboard-anim"
        style="--dashboard-anim-index: 5"
        :label="t('dashboard.stats.openDemands')"
        :loading="loading"
        :value="openDemandsCount"
        accent-var="var(--p-teal-500)"
        :ring="{
          max: demandsCount,
          colorVar: 'var(--p-teal-500)',
          trackColorVar: 'var(--p-teal-100)',
        }"
        clickable
        @click="router.push('/procurement/bought-items-demand')"
      />
      <StatTile
        class="dashboard-anim"
        style="--dashboard-anim-index: 6"
        :label="t('dashboard.stats.ordersLast30Days')"
        :loading="loading"
        :value="recentOrdersCount"
        icon="mdi mdi-cart-outline"
        accent-var="var(--p-purple-500)"
        clickable
        @click="router.push('/procurement/orders')"
      />
      <StatTile
        v-if="hostStore.todosEnabled"
        class="dashboard-anim"
        style="--dashboard-anim-index: 7"
        :label="t('dashboard.stats.tasksDueNow')"
        :loading="todoLoading"
        :value="todoDueNowCount"
        icon="mdi mdi-checkbox-marked-outline"
        accent-var="var(--p-yellow-500)"
        clickable
        @click="router.push('/todo')"
      />
    </div>

    <div class="dashboard-grid">
      <!-- Row 1: what needs doing -->
      <TodoSummaryPanel
        v-if="hostStore.todosEnabled"
        class="dashboard-anim"
        style="--dashboard-anim-index: 8"
        :overdue="todoOverdue"
        :today="todoToday"
        :loading="todoLoading"
      />
      <ShopFloorPanel
        v-if="productionPlanningEnabled"
        class="dashboard-anim"
        style="--dashboard-anim-index: 9"
        :overdue-orders="overdueOrders"
        :today-orders="todayOrders"
        :loading="loading"
      />
      <AlertsPanel class="dashboard-anim" style="--dashboard-anim-index: 10" />

      <!-- Row 2: where work stands -->
      <WipProgressPanel
        v-if="productionPlanningEnabled"
        class="dashboard-anim"
        style="--dashboard-anim-index: 11"
        :wip-lots="wipLots"
        :loading="loading"
      />
      <DemandPipelinePanel
        class="dashboard-anim"
        style="--dashboard-anim-index: 12"
        :made-counts="madeDemandCounts"
        :bought-counts="boughtDemandCounts"
        :source-counts="sourceDemandCounts"
        :loading="loading"
      />
      <RecentItemsPanel
        class="dashboard-anim"
        style="--dashboard-anim-index: 13"
        :items="recentItems"
        :loading="loading"
      />

      <!-- Row 3: the spend chart earns the extra width; quick links need none -->
      <SpendingPanel
        class="dashboard-panel-wide dashboard-anim"
        style="--dashboard-anim-index: 14"
        :spent-recently-cents="spentRecentlyCents"
        :orders-count="recentOrdersCount"
        :daily-spend-series="dailySpendSeries"
        :loading="loading"
      />
      <QuickLinksPanel class="dashboard-anim" style="--dashboard-anim-index: 15" />
    </div>
  </div>
</template>

<style scoped lang="scss">
.dashboard-view {
  height: 100%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-3);
}

// The header and KPI row size to their content at every width, so they
// never shrink below their own text on a short viewport.
.dashboard-view > :not(.dashboard-grid) {
  flex-shrink: 0;
}

.dashboard-kpi-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
  gap: var(--space-3);
}

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);

  // Roomier than the shared .card padding, scoped to the dashboard.
  > * {
    min-height: 15rem;
    padding: var(--space-4) var(--space-4);
  }
}

.dashboard-panel-wide {
  grid-column: span 2;
}

// With enough room the dashboard fits the viewport exactly and long lists
// scroll inside their tile. Below these thresholds the page scrolls.
@media (min-width: $bp-xl) and (min-height: $bp-height-grid) {
  .dashboard-view {
    overflow: hidden;
  }

  .dashboard-grid {
    // A zero basis grows into exactly the leftover space; auto overshot by a
    // few rounded pixels.
    flex: 1 1 0;
    min-height: 0;
    grid-template-rows: repeat(3, minmax(0, 1fr));
    overflow: hidden;

    > * {
      min-height: 0;
    }
  }
}

@media (max-width: $bp-xl) {
  .dashboard-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: $bp-sm) {
  .dashboard-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .dashboard-panel-wide {
    grid-column: span 1;
  }
}

.dashboard-anim {
  animation: dashboard-fade-in 0.45s ease-out both;
  animation-delay: calc(var(--dashboard-anim-index, 0) * 60ms);
}

@media (prefers-reduced-motion: reduce) {
  .dashboard-anim {
    animation: none;
  }
}

@keyframes dashboard-fade-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
