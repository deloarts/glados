<script setup lang="ts">
import { watch } from 'vue'

import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import { useServerTable } from '@/core/composables/useServerTable'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { LiveResource } from '@/core/realtime/resources'
import { storeToRefs } from 'pinia'

import QaControls from '../components/QaControls.vue'
import QaViews from '../components/QaViews.vue'
import QaTaskTable from '../components/QaTaskTable.vue'
import { useQaFiltersStore } from '../stores/qaFiltersStore'
import { useQaTasksStore } from '../stores/qaTasksStore'

const tasksStore = useQaTasksStore()
const filtersStore = useQaFiltersStore()
const { loading } = storeToRefs(tasksStore)
watchLoadingBar(loading)

// The view owns the page window; useServerTable loads on mount.
const { first, rows, fetchItems, resetAndFetch, resetAndFetchDebounced, onPage } = useServerTable({
  fetchParams: ({ first, rows }) => ({ skip: first, limit: rows }),
  fetch: (page) => tasksStore.refresh(page),
})

// Every filter and the sort apply server-side. resetAndFetch, so a narrower
// filter never strands the table on an empty page; refresh() keeps the
// table visible meanwhile.
watch(
  () => [
    filtersStore.showCompleted,
    filtersStore.showCanceled,
    filtersStore.showFuture,
    filtersStore.search,
    filtersStore.sortBy,
    filtersStore.sortDir,
    filtersStore.clearTrigger,
    filtersStore.statuses,
    filtersStore.inspectionMethodIds,
    filtersStore.finishedByIds,
    filtersStore.plannedStartFrom,
    filtersStore.plannedStartTo,
    filtersStore.finishedFrom,
    filtersStore.finishedTo,
  ],
  () => resetAndFetch(),
)

// Typed column filters debounce so a fetch does not fire on every
// keystroke; the pickers and date ranges above refetch at once.
watch(
  () => [
    filtersStore.lotNumber,
    filtersStore.projectNumber,
    filtersStore.itemText,
    filtersStore.quantityMin,
    filtersStore.quantityMax,
  ],
  () => resetAndFetchDebounced(),
)

// Readiness changes with order events and evidence with uploads. Stays on
// the current page.
useLiveRefresh([LiveResource.PRODUCTION_ORDERS, LiveResource.PRODUCTION_LOTS], () => fetchItems())
</script>

<template>
  <PageLayout>
    <template #controls>
      <QaControls />
    </template>
    <template #views>
      <QaViews />
    </template>
    <QaTaskTable :first="first" :rows="rows" @page="onPage" />
  </PageLayout>
</template>
