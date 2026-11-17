<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import ProjectBomBoughtTab from './ProjectBomBoughtTab.vue'
import ProjectBomMadeTab from './ProjectBomMadeTab.vue'
import ProjectBomSourceTab from './ProjectBomSourceTab.vue'
import type { BoughtItemDemandResponse } from '@/features/bought-items'
import type { MadeItemDemandResponse } from '@/features/made-items'
import type { SourceItemDemandResponse } from '@/features/source-items'

defineProps<{
  boughtDemands: BoughtItemDemandResponse[]
  madeDemands: MadeItemDemandResponse[]
  sourceDemands: SourceItemDemandResponse[]
  /** One row per item and project, with a Project column, for a bill over several projects. */
  byProject?: boolean
}>()

const { t } = useI18n()

// Its own tab state, not shared with the outer detail tabs. Only the active
// panel is rendered, so the inactive bills cost nothing until opened, which
// is what keeps their per-row thumbnail requests off the initial load.
const activeBom = ref('bought')
</script>

<template>
  <Tabs v-model:value="activeBom" class="bom-tabs fill-tabs fill-tabs--contained fill-tabs--column">
    <TabList>
      <Tab value="bought">{{ t('resources.projects.detail.bom.subTabs.bought') }}</Tab>
      <Tab value="made">{{ t('resources.projects.detail.bom.subTabs.made') }}</Tab>
      <Tab value="source">{{ t('resources.projects.detail.bom.subTabs.source') }}</Tab>
    </TabList>

    <TabPanels>
      <TabPanel value="bought">
        <ProjectBomBoughtTab :demands="boughtDemands" :by-project="byProject" />
      </TabPanel>
      <TabPanel value="made">
        <ProjectBomMadeTab :demands="madeDemands" :by-project="byProject" />
      </TabPanel>
      <TabPanel value="source">
        <ProjectBomSourceTab :demands="sourceDemands" :by-project="byProject" />
      </TabPanel>
    </TabPanels>
  </Tabs>
</template>

<style scoped lang="scss">
// Mirrors the outer .detail-tabs flex chain so the nested DataTables still
// resolve scrollHeight="flex" against a bounded parent.
.bom-tabs {
  height: 100%;

  --p-tabs-tabpanel-padding: var(--space-3) 0 0;
}
</style>
