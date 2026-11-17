<script setup lang="ts">
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Component } from 'vue'

import { useHostStore } from '@/core/host/stores/hostStore'
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
    value: 'customers',
    labelKey: 'main.sidebar.resources.customers',
    icon: 'mdi-account-tie',
    component: asyncTab(() => import('@/features/customers/views/CustomerManagementView.vue')),
  },
  {
    value: 'suppliers',
    labelKey: 'main.sidebar.resources.suppliers',
    icon: 'mdi-store',
    component: asyncTab(() => import('@/features/suppliers/views/SupplierManagementView.vue')),
  },
  {
    value: 'contacts',
    labelKey: 'contacts.tabLabel',
    icon: 'mdi-card-account-mail-outline',
    component: asyncTab(() => import('@/features/contacts/views/ContactManagementView.vue')),
  },
  {
    value: 'article-groups',
    labelKey: 'main.sidebar.resources.articleGroups',
    icon: 'mdi-tag',
    component: asyncTab(() => import('@/features/article-groups/views/ArticleGroupManagementView.vue')),
  },
  {
    value: 'product-families',
    labelKey: 'main.sidebar.resources.productFamilies',
    icon: 'mdi-shape-outline',
    component: asyncTab(
      () => import('@/features/product-families/views/ProductFamilyManagementView.vue'),
    ),
  },
  {
    value: 'fabrication-methods',
    labelKey: 'main.sidebar.resources.fabricationMethods',
    icon: 'mdi-label-variant',
    component: asyncTab(
      () => import('@/features/fabrication-method-management/views/FabricationMethodManagementView.vue'),
    ),
  },
  {
    value: 'inspection-methods',
    labelKey: 'main.sidebar.resources.inspectionMethods',
    icon: 'mdi-clipboard-check-outline',
    component: asyncTab(
      () => import('@/features/inspection-method-management/views/InspectionMethodManagementView.vue'),
    ),
  },
  {
    value: 'product-devices',
    labelKey: 'main.sidebar.resources.productDevices',
    icon: 'mdi-engine-outline',
    component: asyncTab(
      () => import('@/features/product-devices/views/ProductDeviceResourcesView.vue'),
    ),
  },
  {
    value: 'source-item-types',
    labelKey: 'main.sidebar.resources.sourceItemTypes',
    icon: 'mdi-cube-outline',
    component: asyncTab(
      () => import('@/features/source-item-types/views/SourceItemTypeManagementView.vue'),
    ),
  },
  {
    value: 'machines',
    labelKey: 'main.sidebar.resources.machines',
    icon: 'mdi-robot-industrial',
    component: asyncTab(() => import('@/features/production-machines/views/ProductionMachinesView.vue')),
  },
  {
    value: 'machine-pools',
    labelKey: 'main.sidebar.resources.machinePools',
    icon: 'mdi-view-grid-outline',
    component: asyncTab(
      () => import('@/features/production-machines/views/MachinePoolManagementView.vue'),
    ),
  },
  {
    value: 'holidays',
    labelKey: 'main.sidebar.resources.holidays',
    icon: 'mdi-calendar-remove-outline',
    component: asyncTab(() => import('@/features/holidays/views/HolidayManagementView.vue')),
  },
  {
    value: 'printers',
    labelKey: 'main.sidebar.resources.printers',
    icon: 'mdi-printer',
    component: asyncTab(() => import('@/features/printers/views/PrinterManagementView.vue')),
  },
  {
    value: 'print-labels',
    labelKey: 'main.sidebar.resources.printLabels',
    icon: 'mdi-tag-text-outline',
    component: asyncTab(() => import('@/features/print-labels/views/PrintLabelManagementView.vue')),
  },
  {
    value: 'print-dockets',
    labelKey: 'main.sidebar.resources.printDockets',
    icon: 'mdi-file-document-outline',
    component: asyncTab(() => import('@/features/print-dockets/views/PrintDocketManagementView.vue')),
  },
  {
    value: 'terminals',
    labelKey: 'terminals.tabLabel',
    icon: 'mdi-monitor-dashboard',
    component: asyncTab(() => import('@/features/terminals/views/TerminalsView.vue')),
  },
  {
    value: 'infoscreens',
    labelKey: 'infoscreens.tabLabel',
    icon: 'mdi-television-guide',
    component: asyncTab(() => import('@/features/infoscreens/views/InfoscreensView.vue')),
  },
]

const VALID_TABS = new Set(TABS.map((tab) => tab.value))

const { t } = useI18n()
const hostStore = useHostStore()

// The device lists go with the devices feature.
function tabAllowed(tab: string): boolean {
  return tab !== 'product-devices' || hostStore.devicesEnabled
}
const { tabOffered } = usePhoneLayout()
const shownTabs = computed(() =>
  TABS.filter((tab) => tabAllowed(tab.value) && tabOffered(tab.value)),
)

const activeTab = useRouteTab({
  param: 'tab',
  validTabs: VALID_TABS,
  defaultTab: 'customers',
  basePath: '/resources',
  isAllowed: tabAllowed,
})
watch(
  () => tabAllowed(activeTab.value),
  (allowed) => {
    if (!allowed) activeTab.value = 'customers'
  },
)
</script>

<template>
  <div class="section-view">
    <Tabs v-model:value="activeTab" class="section-tabs fill-tabs fill-tabs--contained">
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
