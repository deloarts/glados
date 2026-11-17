<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import { TABLES } from '../registry'

/**
 * The reference tables, one tab each: values that are looked up, such as
 * general tolerances and thread data. Nothing here is saved, so the page has
 * no info or controls bar.
 */

const VALID_TABS = new Set(TABLES.map((table) => table.tab))
const DEFAULT_TAB = TABLES[0]?.tab ?? ''

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const activeTab = computed({
  get: () => {
    const param = route.params.tab
    return typeof param === 'string' && VALID_TABS.has(param) ? param : DEFAULT_TAB
  },
  set: (tab: string) => {
    if (tab !== route.params.tab) void router.replace(`/tables/${tab}`)
  },
})
</script>

<template>
  <div class="section-view">
    <Tabs v-model:value="activeTab" class="section-tabs fill-tabs fill-tabs--contained">
      <TabList>
        <Tab v-for="table in TABLES" :key="table.tab" :value="table.tab" :data-testid="`tables-tab-${table.tab}`">
          <i :class="`mdi ${table.icon} tab-icon`" aria-hidden="true" />
          {{ t(table.labelKey) }}
        </Tab>
      </TabList>
      <TabPanels>
        <TabPanel v-for="table in TABLES" :key="table.tab" :value="table.tab">
          <PageLayout v-if="activeTab === table.tab" :card="false">
            <component :is="table.component" />
          </PageLayout>
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
