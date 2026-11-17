<script setup lang="ts">
// The catalogue section page. It sits above the contexts because it hands
// the item catalogues the order and lot dialogs their rows open, which belong
// to Planning and fulfillment; the item features themselves never import
// those features.
import { useI18n } from 'vue-i18n'
import { provide, type Component } from 'vue'

// The tabs are lazy-loaded via the asyncTab helper
import { asyncTab } from '@/shared/utils/asyncTab'
import { useRouteTab } from '@/shared/composables/useRouteTab'
import { boughtItemOrderDialogsKey } from '@/features/bought-items'
import { madeItemLotDialogsKey } from '@/features/made-items'
import { BoughtItemAddToOrderDialog, BoughtItemOrderHistoryDialog } from '@/features/orders'
import { MadeItemHistoryDialog } from '@/features/production'

interface TabConfig {
  value: string
  labelKey: string
  icon: string
  component: Component
}

const TABS: TabConfig[] = [
  {
    value: 'bought-items',
    labelKey: 'main.sidebar.boughtItems.label',
    icon: 'mdi-package',
    component: asyncTab(() => import('@/features/bought-items/views/BoughtItemCatalogueView.vue')),
  },
  {
    value: 'made-items',
    labelKey: 'main.sidebar.madeItems.label',
    icon: 'mdi-factory',
    component: asyncTab(() => import('@/features/made-items/views/MadeItemCatalogueView.vue')),
  },
  {
    value: 'source-items',
    labelKey: 'main.sidebar.sourceItems.label',
    icon: 'mdi-cube-outline',
    component: asyncTab(() => import('@/features/source-items/views/SourceItemCatalogueView.vue')),
  },
]

const VALID_TABS = new Set(TABS.map((tab) => tab.value))

provide(boughtItemOrderDialogsKey, {
  addToOrder: BoughtItemAddToOrderDialog,
  orderHistory: BoughtItemOrderHistoryDialog,
})
provide(madeItemLotDialogsKey, { history: MadeItemHistoryDialog })

const { t } = useI18n()

const activeTab = useRouteTab({
  param: 'tab',
  validTabs: VALID_TABS,
  defaultTab: 'bought-items',
  basePath: '/catalogue',
})
</script>

<template>
  <div class="section-view">
    <Tabs v-model:value="activeTab" class="section-tabs fill-tabs">
      <TabList>
        <Tab v-for="tab in TABS" :key="tab.value" :value="tab.value">
          <i :class="`mdi ${tab.icon} tab-icon`" aria-hidden="true" />
          {{ t(tab.labelKey) }}
        </Tab>
      </TabList>
      <TabPanels>
        <TabPanel v-for="tab in TABS" :key="tab.value" :value="tab.value">
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
