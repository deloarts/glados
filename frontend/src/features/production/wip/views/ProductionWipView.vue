<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { getProductionWip } from '../api/getProductionWip'
import ProductionWipTable from '../components/ProductionWipTable.vue'
import { formatISOTime } from '@/core/utils/dates'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { LiveResource } from '@/core/realtime/resources'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { HelpButton } from '@/shared/help'

import type { WipLotResponse } from '../types/productionWipResponse'

const { t } = useI18n()

const lots = ref<WipLotResponse[]>([])
const tableRef = ref<InstanceType<typeof ProductionWipTable> | null>(null)
const hasActiveFilters = computed(() => tableRef.value?.hasActiveFilters ?? false)
const loading = ref(false)
watchLoadingBar(loading)
const lastUpdated = ref<Date | null>(null)

// Formats the client clock in the tenant's timezone.
const lastUpdatedLabel = computed(() =>
  lastUpdated.value ? formatISOTime(lastUpdated.value.toISOString()) : '',
)

async function fetchWip(): Promise<void> {
  loading.value = true
  try {
    lots.value = await getProductionWip()
    lastUpdated.value = new Date()
  } catch {
    // The rows stay on screen and the last-updated time shows their age. The
    // next live signal, reconnect or manual sync retries.
  } finally {
    loading.value = false
  }
}

// Lots, their positions and steps, production orders and order items signal
// on these resources, and the machines carry the names in the stages. The
// reconnect catch-up covers what was missed offline, so the view needs no
// poll.
useLiveRefresh(
  [LiveResource.PRODUCTION_LOTS, LiveResource.PRODUCTION_ORDERS, LiveResource.PRODUCTION_MACHINES],
  fetchWip,
)

onMounted(() => void fetchWip())
</script>

<template>
  <PageLayout :card="false">
    <template #controls>
      <ControlsBar>
        <template #start>
          <Tag
            v-if="loading"
            :value="t('productionWip.autoRefreshing')"
            icon="mdi mdi-progress-clock"
            severity="info"
          />
          <Tag
            v-else-if="lastUpdated"
            :value="t('productionWip.lastUpdated', { time: lastUpdatedLabel })"
            icon="mdi mdi-clock-outline"
            severity="secondary"
          />
        </template>
        <template #handbook>
          <HelpButton rounded />
        </template>
      </ControlsBar>
    </template>
    <template #views>
      <ViewsBar
        id-prefix="production-wip"
        hide-views-toggle
        :syncing="loading"
        :has-active-filters="hasActiveFilters"
        @sync="fetchWip"
        @clear="tableRef?.clearFilters()"
      />
    </template>

    <ProductionWipTable ref="tableRef" :lots="lots" />
  </PageLayout>
</template>
