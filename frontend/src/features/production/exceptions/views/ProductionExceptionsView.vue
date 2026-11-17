<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { getPlanningExceptions } from '../api/getPlanningExceptions'
import PlanningExceptionsTable from '../components/PlanningExceptionsTable.vue'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { LiveResource } from '@/core/realtime/resources'
import { HelpButton } from '@/shared/help'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import InfoBar from '@/shared/components/resource-view/InfoBar.vue'
import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'

import {
  PLANNING_EXCEPTION_KINDS,
  PLANNING_EXCEPTION_SEVERITY,
} from '../utils/planningExceptionKinds'

import type { PlanningExceptionResponse } from '../types/planningExceptionResponse'

const { t } = useI18n()

const rows = ref<PlanningExceptionResponse[]>([])
const loading = ref(false)
watchLoadingBar(loading)

async function fetchExceptions(): Promise<void> {
  loading.value = true
  try {
    rows.value = await getPlanningExceptions()
  } catch {
    // The rows stay on screen; the next live signal or a manual sync retries.
  } finally {
    loading.value = false
  }
}

// The exceptions follow the lots, their production orders, the order lines
// and the demands of every family, so any of them signals a refresh.
useLiveRefresh(
  [
    LiveResource.PRODUCTION_LOTS,
    LiveResource.PRODUCTION_ORDERS,
    LiveResource.ORDERS,
    LiveResource.BOUGHT_ITEM_DEMANDS,
    LiveResource.MADE_ITEM_DEMANDS,
    LiveResource.SOURCE_ITEM_DEMANDS,
  ],
  fetchExceptions,
)

onMounted(() => void fetchExceptions())

// One count per kind that has rows, in the order the list sorts them.
const kindCounts = computed(() =>
  PLANNING_EXCEPTION_KINDS.map((kind) => ({
    kind,
    count: rows.value.filter((row) => row.kind === kind).length,
  })).filter((entry) => entry.count > 0),
)
</script>

<template>
  <PageLayout>
    <template #info>
      <InfoBar>
        <span class="info-title">{{ t('productionExceptions.title') }}</span>
        <span class="info-sep" />
        <span class="info-muted">{{ t('productionExceptions.count', rows.length) }}</span>
        <template v-if="kindCounts.length">
          <span class="info-sep" />
          <span class="info-tags">
            <Tag
              v-for="entry in kindCounts"
              :key="entry.kind"
              :value="`${t(`productionExceptions.kind.${entry.kind}`)} ${entry.count}`"
              :severity="PLANNING_EXCEPTION_SEVERITY[entry.kind]"
            />
          </span>
        </template>
      </InfoBar>
    </template>
    <template #views>
      <ViewsBar
        id-prefix="production-exceptions"
        hide-views-toggle
        :syncing="loading"
        :has-active-filters="false"
        @sync="fetchExceptions"
      >
        <!-- The tab has no actions and so no controls bar, which leaves the
             views bar to close with the handbook button. -->
        <template #end>
          <HelpButton rounded slug="production/planning-exceptions" />
        </template>
      </ViewsBar>
    </template>

    <PlanningExceptionsTable :rows="rows" />
  </PageLayout>
</template>

<style scoped lang="scss">
.info-title {
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.info-muted {
  font-size: var(--font-size-lg);
  color: var(--p-text-muted-color);
}

.info-tags {
  display: inline-flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}
</style>
