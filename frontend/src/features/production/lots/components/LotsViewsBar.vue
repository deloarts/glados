<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { useProductionLotsFiltersStore } from '../stores/productionLotsFiltersStore'
import { useProductionLotsStore } from '../../stores/productionLotsStore'

import type { MenuItem } from 'openvue/menuitem'

// The lots list's views bar. `compact` puts the modes and the quick filters
// behind two split buttons, for a bar that would not fit on one row (see
// LotsViews).
defineProps<{
  compact?: boolean
}>()

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const filtersStore = useProductionLotsFiltersStore()
const lotsStore = useProductionLotsStore()
const { search, sortBy, groupBy } = storeToRefs(filtersStore)

const isTimelineOpen = computed(() => route.name === 'ProductionLotsTimeline')

function toggleTimeline(): void {
  void router.push(isTimelineOpen.value ? '/production/lots' : '/production/lots/timeline')
}

const sortByItems = computed<MenuItem[]>(() => [
  {
    label: t('production.lots.views.sortByItems.lotNumberAsc'),
    icon: 'mdi mdi-sort-alphabetical-ascending',
    command: () => filtersStore.setSort('lot_number', 'asc'),
  },
  {
    label: t('production.lots.views.sortByItems.lotNumberDesc'),
    icon: 'mdi mdi-sort-alphabetical-descending',
    command: () => filtersStore.setSort('lot_number', 'desc'),
  },
  {
    label: t('production.lots.views.sortByItems.createdDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => filtersStore.setSort('created', 'desc'),
  },
  {
    label: t('production.lots.views.sortByItems.createdAsc'),
    icon: 'mdi mdi-sort-clock-ascending',
    command: () => filtersStore.setSort('created', 'asc'),
  },
  {
    label: t('production.lots.views.sortByItems.quantityDesc'),
    icon: 'mdi mdi-sort-numeric-descending',
    command: () => filtersStore.setSort('quantity', 'desc'),
  },
  {
    label: t('production.lots.views.sortByItems.quantityAsc'),
    icon: 'mdi mdi-sort-numeric-ascending',
    command: () => filtersStore.setSort('quantity', 'asc'),
  },
])

// A DataTable can only run one rowGroupMode at a time, and Column Mode
// already claims it (rowspan, by lot), so picking a group switches the
// table into Widescreen Mode (see setGroupBy), and the Widescreen toggle
// stays disabled for as long as that group is active.
const groupByItems = computed<MenuItem[]>(() => [
  {
    label: t('production.lots.views.groupByItems.status'),
    icon: 'mdi mdi-flag-outline',
    command: () => filtersStore.setGroupBy('status'),
  },
  {
    label: t('production.lots.views.groupByItems.priority'),
    icon: 'mdi mdi-priority-high',
    command: () => filtersStore.setGroupBy('priority'),
  },
  {
    label: t('production.lots.views.groupByItems.project'),
    icon: 'mdi mdi-folder-outline',
    command: () => filtersStore.setGroupBy('project'),
  },
])

type LotsMode = 'column' | 'simple' | 'widescreen'

const mode = computed<LotsMode>(() => {
  if (filtersStore.simpleMode) return 'simple'
  return filtersStore.widescreenMode ? 'widescreen' : 'column'
})

function setMode(next: LotsMode): void {
  if ((next === 'simple') !== filtersStore.simpleMode) filtersStore.toggleSimpleMode()
  if (next === 'simple') return
  if ((next === 'widescreen') !== filtersStore.widescreenMode) filtersStore.toggleWidescreenMode()
}

function checkIcon(on: boolean): string {
  return on ? 'mdi mdi-checkbox-marked-outline' : 'mdi mdi-checkbox-blank-outline'
}

// The button itself goes back to Column Mode, the default, unless a group
// keeps the table in Widescreen Mode.
function resetMode(): void {
  if (!groupBy.value) setMode('column')
}

const modeLabel = computed(() => t(`production.lots.views.modes.${mode.value}`))

// Grouping runs in Widescreen Mode only, so Column Mode waits until the
// group is cleared, as the Widescreen toggle of the full bar does.
const modeItems = computed<MenuItem[]>(() => [
  {
    label: t('production.lots.views.modes.column'),
    icon: checkIcon(mode.value === 'column'),
    disabled: !!groupBy.value,
    command: () => setMode('column'),
  },
  {
    label: t('production.lots.views.modes.simple'),
    icon: checkIcon(mode.value === 'simple'),
    command: () => setMode('simple'),
  },
  {
    label: t('production.lots.views.modes.widescreen'),
    icon: checkIcon(mode.value === 'widescreen'),
    command: () => setMode('widescreen'),
  },
])

const quickFilterCount = computed(
  () =>
    [
      filtersStore.hideCompleted,
      filtersStore.hideCanceled,
      filtersStore.needsAssignmentOnly,
      filtersStore.needsApprovalOnly,
    ].filter(Boolean).length,
)

const quickFiltersLabel = computed(() =>
  quickFilterCount.value > 0
    ? t('production.lots.views.quickFiltersCount', { n: quickFilterCount.value })
    : t('production.lots.views.quickFilters'),
)

// The smart filter is on by default, so it shows its state but does not
// count as a set filter, as on the full bar.
const quickFilterItems = computed<MenuItem[]>(() => [
  {
    label: t('production.lots.views.hideCompleted'),
    icon: checkIcon(filtersStore.hideCompleted),
    command: () => filtersStore.toggleHideCompleted(),
  },
  {
    label: t('production.lots.views.hideCanceled'),
    icon: checkIcon(filtersStore.hideCanceled),
    command: () => filtersStore.toggleHideCanceled(),
  },
  {
    label: t('production.lots.views.needsAssignment'),
    icon: checkIcon(filtersStore.needsAssignmentOnly),
    command: () => filtersStore.toggleNeedsAssignmentOnly(),
  },
  {
    label: t('production.lots.views.needsApproval'),
    icon: checkIcon(filtersStore.needsApprovalOnly),
    command: () => filtersStore.toggleNeedsApprovalOnly(),
  },
  { separator: true },
  {
    label: t('production.lots.views.smartFilter'),
    icon: checkIcon(filtersStore.smartFilterEnabled),
    command: () => filtersStore.toggleSmartFilter(),
  },
])

// The button itself clears the four quick filters, as Group By and Sort By
// clear theirs.
function clearQuickFilters(): void {
  if (filtersStore.hideCompleted) filtersStore.toggleHideCompleted()
  if (filtersStore.hideCanceled) filtersStore.toggleHideCanceled()
  if (filtersStore.needsAssignmentOnly) filtersStore.toggleNeedsAssignmentOnly()
  if (filtersStore.needsApprovalOnly) filtersStore.toggleNeedsApprovalOnly()
}
</script>

<template>
  <ViewsBar
    id-prefix="lots"
    hide-views-toggle
    :group-by-items="groupByItems"
    :group-by-active="!!groupBy"
    :sort-by-items="sortByItems"
    :sort-by-active="!!sortBy"
    :has-active-filters="filtersStore.hasActiveFilters"
    v-model:search="search"
    :search-placeholder="t('production.lots.controls.search')"
    @sync="lotsStore.triggerRefresh()"
    @clear-group-by="filtersStore.clearGroupBy()"
    @clear-sort-by="filtersStore.clearSort()"
    @clear="filtersStore.clearAll()"
  >
    <template #start-extra>
      <Button
        :label="
          isTimelineOpen
            ? t('production.lots.views.closeTimeline')
            : t('production.lots.views.openTimeline')
        "
        :icon="isTimelineOpen ? 'mdi mdi-format-list-bulleted' : 'mdi mdi-chart-gantt'"
        severity="contrast"
        :text="!isTimelineOpen"
        @click="toggleTimeline"
      />
      <SplitButton
        v-if="compact"
        :label="modeLabel"
        icon="mdi mdi-table-cog"
        severity="contrast"
        :text="mode === 'column'"
        :model="modeItems"
        data-testid="lots-views-modes"
        @click="resetMode"
      />
      <template v-else>
        <Button
          :label="t('production.lots.views.simpleMode')"
          icon="mdi mdi-table-large"
          severity="contrast"
          :text="!filtersStore.simpleMode"
          @click="filtersStore.toggleSimpleMode()"
        />
        <Button
          :label="t('production.lots.views.widescreenMode')"
          icon="mdi mdi-view-column-outline"
          severity="contrast"
          :text="!filtersStore.widescreenMode"
          :disabled="filtersStore.simpleMode || !!filtersStore.groupBy"
          @click="filtersStore.toggleWidescreenMode()"
        />
      </template>
    </template>
    <template #extra>
      <Divider layout="vertical" />
      <SplitButton
        v-if="compact"
        :label="quickFiltersLabel"
        icon="mdi mdi-filter-variant"
        severity="contrast"
        :text="quickFilterCount === 0"
        :model="quickFilterItems"
        data-testid="lots-views-quick-filters"
        @click="clearQuickFilters"
      />
      <template v-else>
        <Button
          :label="t('production.lots.views.hideCompleted')"
          icon="mdi mdi-check-circle-outline"
          severity="contrast"
          :text="!filtersStore.hideCompleted"
          @click="filtersStore.toggleHideCompleted()"
        />
        <Button
          :label="t('production.lots.views.hideCanceled')"
          icon="mdi mdi-cancel"
          severity="contrast"
          :text="!filtersStore.hideCanceled"
          @click="filtersStore.toggleHideCanceled()"
        />
        <Button
          :label="t('production.lots.views.needsAssignment')"
          icon="mdi mdi-clipboard-alert-outline"
          severity="contrast"
          :text="!filtersStore.needsAssignmentOnly"
          v-tooltip.bottom="t('production.lots.views.needsAssignmentTooltip')"
          @click="filtersStore.toggleNeedsAssignmentOnly()"
        />
        <Button
          :label="t('production.lots.views.needsApproval')"
          icon="mdi mdi-check-decagram-outline"
          severity="contrast"
          :text="!filtersStore.needsApprovalOnly"
          v-tooltip.bottom="t('production.lots.views.needsApprovalTooltip')"
          @click="filtersStore.toggleNeedsApprovalOnly()"
        />
        <Button
          :label="
            filtersStore.smartFilterEnabled
              ? t('production.lots.views.smartFilterOn')
              : t('production.lots.views.smartFilterOff')
          "
          icon="mdi mdi-filter-variant"
          severity="contrast"
          text
          v-tooltip.bottom="t('production.lots.views.smartFilterTooltip')"
          @click="filtersStore.toggleSmartFilter()"
        />
      </template>
    </template>
  </ViewsBar>
</template>
