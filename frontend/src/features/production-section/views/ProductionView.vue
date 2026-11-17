<script setup lang="ts">
// The production section page. It is a feature of its own so it can host
// the QA tab next to the production tabs: QA builds on production, so
// production itself must not import it.
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { Component } from 'vue'

import { usePhoneLayout } from '@/core/composables/usePhoneLayout'
import { asyncTab } from '@/shared/utils/asyncTab'

interface TabConfig {
  value: string
  labelKey: string
  icon: string
  component: Component
}

const TABS: TabConfig[] = [
  {
    value: 'lots',
    labelKey: 'production.lots.tabLabel',
    icon: 'mdi-ticket-confirmation-outline',
    component: asyncTab(() => import('@/features/production/lots/views/ProductionLotsListView.vue')),
  },
  {
    value: 'queue',
    labelKey: 'productionQueue.tabLabel',
    icon: 'mdi-view-column',
    component: asyncTab(() => import('@/features/production/queue/views/ProductionQueueView.vue')),
  },
  {
    value: 'planning',
    labelKey: 'productionPlanning.tabLabel',
    icon: 'mdi-chart-gantt',
    component: asyncTab(() => import('@/features/production/planning/views/ProductionPlanningView.vue')),
  },
  {
    value: 'wip',
    labelKey: 'productionWip.tabLabel',
    icon: 'mdi-progress-clock',
    component: asyncTab(() => import('@/features/production/wip/views/ProductionWipView.vue')),
  },
  {
    value: 'exceptions',
    labelKey: 'productionExceptions.tabLabel',
    icon: 'mdi-alert-circle-outline',
    component: asyncTab(() => import('@/features/production/exceptions/views/ProductionExceptionsView.vue')),
  },
  {
    value: 'capacity',
    labelKey: 'productionSchedule.tabLabel',
    icon: 'mdi-calendar-clock',
    component: asyncTab(() => import('@/features/production/planning/views/ProductionCapacityView.vue')),
  },
  {
    value: 'qa',
    labelKey: 'productionQa.tabLabel',
    icon: 'mdi-clipboard-check-outline',
    component: asyncTab(() => import('@/features/production-qa/views/ProductionQaView.vue')),
  },
  {
    value: 'kpi',
    labelKey: 'productionKpi.tabLabel',
    icon: 'mdi-speedometer',
    component: asyncTab(() => import('@/features/production/kpi/views/ProductionKpiView.vue')),
  },
]

const VALID_TABS = new Set(TABS.map((tab) => tab.value))
const LOTS_ROUTE_NAMES = new Set(['ProductionLots', 'ProductionLotsTimeline'])

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const { tabOffered } = usePhoneLayout()
const shownTabs = computed(() => TABS.filter((tab) => tabOffered(tab.value)))

function resolveTab(): string {
  if (typeof route.name === 'string' && LOTS_ROUTE_NAMES.has(route.name)) return 'lots'
  const param = route.params.tab
  return typeof param === 'string' && VALID_TABS.has(param) ? param : 'queue'
}

const activeTab = ref(resolveTab())

watch(activeTab, (tab) => {
  void router.replace(`/production/${tab}`)
})

watch(
  () => [route.name, route.params.tab],
  () => {
    const tab = resolveTab()
    if (tab !== activeTab.value) activeTab.value = tab
  },
)
</script>

<template>
  <div class="section-view">
    <Tabs v-model:value="activeTab" class="section-tabs fill-tabs">
      <TabList>
        <Tab v-for="tab in shownTabs" :key="tab.value" :value="tab.value">
          <i :class="`mdi ${tab.icon} tab-icon`" aria-hidden="true" />
          {{ t(tab.labelKey) }}
        </Tab>
      </TabList>
      <TabPanels>
        <TabPanel v-for="tab in shownTabs" :key="tab.value" :value="tab.value">
          <component v-if="activeTab === tab.value" :is="tab.component" />
        </TabPanel>
      </TabPanels>
    </Tabs>
  </div>
</template>

<style scoped lang="scss">
.section-view {
  height: calc(100% + 1rem);
  margin: -0.5rem;
}

.section-tabs {
  height: 100%;
}

.tab-icon {
  margin-right: var(--space-1);
}
</style>
