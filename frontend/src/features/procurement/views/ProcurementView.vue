<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Component } from 'vue'

import { usePhoneLayout } from '@/core/composables/usePhoneLayout'

import { asyncTab } from '@/shared/utils/asyncTab'
import { useRouteTab } from '@/shared/composables/useRouteTab'

interface TabConfig {
  value: string
  labelKey: string
  icon: string
  component: Component
}

const TABS: TabConfig[] = [
  {
    value: 'orders',
    labelKey: 'procurement.sections.orders',
    icon: 'mdi-cart',
    component: asyncTab(() => import('@/features/orders/views/OrdersView.vue')),
  },
  {
    value: 'quotes',
    labelKey: 'procurement.sections.quotes',
    icon: 'mdi-scale-balance',
    component: asyncTab(() => import('@/features/quote-requests/views/QuoteRequestsView.vue')),
  },
  {
    value: 'external-work',
    labelKey: 'procurement.sections.externalWork',
    icon: 'mdi-truck-delivery-outline',
    component: asyncTab(() => import('@/features/procurement/views/ExternalWorkView.vue')),
  },
  {
    value: 'bought-items-demand',
    labelKey: 'procurement.sections.boughtItemsDemand',
    icon: 'mdi-format-list-checks',
    component: asyncTab(() => import('@/features/procurement/views/BoughtItemDemandsView.vue')),
  },
  {
    value: 'made-items-demand',
    labelKey: 'procurement.sections.madeItemsDemand',
    icon: 'mdi-format-list-checks',
    component: asyncTab(() => import('@/features/production/made-item-demands/views/MadeItemDemandsView.vue')),
  },
  {
    value: 'source-items-demand',
    labelKey: 'procurement.sections.sourceItemsDemand',
    icon: 'mdi-format-list-checks',
    component: asyncTab(() => import('@/features/production/source-item-demands/views/SourceItemDemandsView.vue')),
  },
]

const VALID_TABS = new Set(TABS.map((tab) => tab.value))

const { t } = useI18n()
const { tabOffered } = usePhoneLayout()
const shownTabs = computed(() => TABS.filter((tab) => tabOffered(tab.value)))

const activeTab = useRouteTab({
  param: 'section',
  validTabs: VALID_TABS,
  defaultTab: 'orders',
  basePath: '/procurement',
})
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
