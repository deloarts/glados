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
    value: 'products',
    labelKey: 'main.sidebar.workspace.products',
    icon: 'mdi-package-variant',
    component: asyncTab(() => import('@/features/products/views/ProductsManagementView.vue')),
  },
  {
    value: 'projects',
    labelKey: 'main.sidebar.workspace.projects',
    icon: 'mdi-briefcase',
    component: asyncTab(() => import('@/features/projects/views/ProjectsManagementView.vue')),
  },
]

const VALID_TABS = new Set(TABS.map((tab) => tab.value))

const { t } = useI18n()
const { phoneMode, tabOffered } = usePhoneLayout()
const shownTabs = computed(() => TABS.filter((tab) => tabOffered(tab.value)))

// A phone offers projects only, so it opens on them.
const activeTab = useRouteTab({
  param: 'tab',
  validTabs: VALID_TABS,
  defaultTab: phoneMode.value ? 'projects' : 'products',
  basePath: '/workspace',
})
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
