<script setup lang="ts">
// The KPI page's #views bar: a period preset (with a custom range picker),
// and machine/pool, project and customer scope filters. No search/sort/
// group here, so ViewsBar's own toggle is hidden and only its sync/clear
// chrome is used, with the actual filter controls in its extra slot, which
// ViewsBar renders between its two vertical dividers.
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'

import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { HelpButton } from '@/shared/help'
import ProjectSelect from '@/shared/components/project/ProjectSelect.vue'
import { CustomerSelect } from '@/features/customers'
import KpiMachineOrPoolSelect from './KpiMachineOrPoolSelect.vue'
import { useProductionKpiStore } from '../stores/productionKpiStore'
import { PRESET_PERIODS } from '../utils/periodPresets'

import type { ProductionKpiPeriodPreset } from '../utils/periodPresets'

const { t } = useI18n()
const store = useProductionKpiStore()
const {
  periodPreset,
  customRange,
  machineOrPoolKey,
  selectedProject,
  selectedCustomer,
  loading,
  hasActiveFilters,
} = storeToRefs(store)

const presetOptions = computed(() => [
  ...PRESET_PERIODS.map((preset) => ({
    value: preset,
    label: t(`productionKpi.filters.periodPresets.${preset}`),
  })),
  { value: 'custom' as ProductionKpiPeriodPreset, label: t('productionKpi.filters.periodPresets.custom') },
])

// clearFilters() resets the same refs the parent view's watcher observes,
// so that watcher re-fetches; no explicit load() needed here, unlike sync.
function onClear(): void {
  store.clearFilters()
}
</script>

<template>
  <ViewsBar
    id-prefix="production-kpi"
    hide-views-toggle
    :syncing="loading"
    :has-active-filters="hasActiveFilters"
    @sync="store.load()"
    @clear="onClear"
  >
    <template #extra>
      <div class="kpi-filter kpi-filter--period">
        <label id="kpi-filter-period-label" for="kpi-filter-period">{{ t('productionKpi.filters.periodLabel') }}</label>
        <Select
          id="kpi-filter-period"
          aria-labelledby="kpi-filter-period-label"
          v-model="periodPreset"
          :options="presetOptions"
          option-label="label"
          option-value="value"
        />
      </div>
      <div v-if="periodPreset === 'custom'" class="kpi-filter kpi-filter--range">
        <label for="kpi-filter-range">{{ t('productionKpi.filters.customRangeLabel') }}</label>
        <DatePicker
          id="kpi-filter-range"
          v-model="customRange"
          selection-mode="range"
          show-button-bar
          :placeholder="t('productionKpi.filters.customRangePlaceholder')"
        />
      </div>
      <div class="kpi-filter kpi-filter--machine">
        <label id="kpi-filter-machine-pool-label" for="kpi-filter-machine-pool">{{ t('productionKpi.filters.machineOrPool') }}</label>
        <KpiMachineOrPoolSelect id="kpi-filter-machine-pool" aria-labelledby="kpi-filter-machine-pool-label" v-model="machineOrPoolKey" />
      </div>
      <div class="kpi-filter kpi-filter--project">
        <label id="kpi-filter-project-label" for="kpi-filter-project">{{ t('productionKpi.filters.project') }}</label>
        <ProjectSelect input-id="kpi-filter-project" aria-labelledby="kpi-filter-project-label" v-model="selectedProject" />
      </div>
      <div class="kpi-filter kpi-filter--customer">
        <label id="kpi-filter-customer-label" for="kpi-filter-customer">{{ t('productionKpi.filters.customer') }}</label>
        <CustomerSelect id="kpi-filter-customer" aria-labelledby="kpi-filter-customer-label" v-model="selectedCustomer" />
      </div>
    </template>
    <!-- The KPI page has no controls bar, so its handbook button sits at the
         far end of this bar. -->
    <template #end>
      <HelpButton rounded />
    </template>
  </ViewsBar>
</template>

<style scoped lang="scss">
.kpi-filter {
  display: flex;
  align-items: center;
  gap: var(--space-2);

  label {
    font-size: var(--font-size-sm);
    color: var(--p-text-muted-color);
    white-space: nowrap;
  }
}

/* stylelint-disable selector-disallowed-list -- the machine, project and customer Selects sit inside wrapper components that do not pass a class on to the Select */
.kpi-filter--period :deep(.p-select),
.kpi-filter--machine :deep(.p-select),
.kpi-filter--project :deep(.p-select),
.kpi-filter--customer :deep(.p-select) {
  min-width: 12rem;
}

.kpi-filter--range :deep(.p-datepicker) {
  min-width: 9rem;
}
/* stylelint-enable selector-disallowed-list */
</style>
