<script setup lang="ts">
// Production KPI dashboard. Every number is computed by the backend for the
// active filter; this view only shapes the response into tiles, charts and
// tables.
import { computed, onMounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'

import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import SectionCard from '@/shared/components/resource-view/SectionCard.vue'
import AsyncChunkLoading from '@/shared/components/layout/AsyncChunkLoading.vue'
import { useKpiFormat } from '../composables/useKpiFormat'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import KpiFiltersBar from '../components/KpiFiltersBar.vue'
import KpiTile from '../components/KpiTile.vue'
import KpiWeeklyChart from '../components/KpiWeeklyChart.vue'
import KpiUtilizationChart from '../components/KpiUtilizationChart.vue'
import KpiEstimateAccuracyPanel from '../components/KpiEstimateAccuracyPanel.vue'
import KpiWaitingTimePanel from '../components/KpiWaitingTimePanel.vue'
import KpiLateLotsTable from '../components/KpiLateLotsTable.vue'
import KpiQualityByItemTable from '../components/KpiQualityByItemTable.vue'
import KpiScrapByReasonChart from '../components/KpiScrapByReasonChart.vue'
import KpiRejectedPerSupplierTable from '../components/KpiRejectedPerSupplierTable.vue'
import { useProductionKpiStore } from '../stores/productionKpiStore'

const { t } = useI18n()
const { formatPercent, formatDays: formatDayCount } = useKpiFormat()
const store = useProductionKpiStore()
const {
  periodPreset,
  customRange,
  machineOrPoolKey,
  selectedProject,
  selectedCustomer,
  summary,
  previousSummary,
  weekly,
  utilization,
  estimateAccuracy,
  waitingTime,
  lateLots,
  qualityByItem,
  scrapByReason,
  rejectedPerSupplier,
  loading,
  error,
} = storeToRefs(store)

watchLoadingBar(loading)

function formatDays(value: number): string {
  return `${formatDayCount(value)} ${t('productionKpi.tiles.daysUnit')}`
}

interface TileData {
  key: string
  label: string
  definition: string
  value: number | null
  previousValue: number | null
  formatValue: (value: number) => string
  naReason: string | null
  note: string | null
  higherIsBetter: boolean
  icon: string
}

// Fixed tiles plus availability and OEE, appended only when computable.
const tiles = computed<TileData[]>(() => {
  const s = summary.value
  if (!s) return []
  const p = previousSummary.value

  const list: TileData[] = [
    {
      key: 'scheduleAdherence',
      label: t('productionKpi.tiles.scheduleAdherence'),
      definition: t('productionKpi.definitions.scheduleAdherence'),
      value: s.schedule_adherence.value,
      previousValue: p?.schedule_adherence.value ?? null,
      formatValue: formatPercent,
      naReason: s.schedule_adherence.value === null ? t('productionKpi.na.noBaseline') : null,
      note:
        s.schedule_adherence.value === null
          ? null
          : t('productionKpi.tiles.sampleOrders', { count: s.schedule_adherence.denominator }),
      higherIsBetter: true,
      icon: 'mdi mdi-calendar-check-outline',
    },
    {
      key: 'onTimeDelivery',
      label: t('productionKpi.tiles.onTimeDelivery'),
      definition: t('productionKpi.definitions.onTimeDelivery'),
      value: s.on_time_delivery.value,
      previousValue: p?.on_time_delivery.value ?? null,
      formatValue: formatPercent,
      naReason: s.on_time_delivery.value === null ? t('productionKpi.na.noTargetDate') : null,
      note:
        s.on_time_delivery.value === null
          ? null
          : t('productionKpi.tiles.sampleLots', { count: s.on_time_delivery.denominator }),
      higherIsBetter: true,
      icon: 'mdi mdi-truck-check-outline',
    },
    {
      key: 'throughputTime',
      label: t('productionKpi.tiles.throughputTime'),
      definition: t('productionKpi.definitions.throughputTime'),
      value: s.throughput_time.median_days,
      previousValue: p?.throughput_time.median_days ?? null,
      formatValue: formatDays,
      naReason: s.throughput_time.count === 0 ? t('productionKpi.na.noCompletedLots') : null,
      note:
        s.throughput_time.count === 0 || s.throughput_time.p90_days === null
          ? null
          : t('productionKpi.tiles.throughputNote', {
              p90: formatDays(s.throughput_time.p90_days),
              count: s.throughput_time.count,
            }),
      higherIsBetter: false,
      icon: 'mdi mdi-timer-sand',
    },
    {
      key: 'utilization',
      label: t('productionKpi.tiles.utilization'),
      definition: t('productionKpi.definitions.utilization'),
      value: s.utilization?.value ?? null,
      previousValue: p?.utilization?.value ?? null,
      formatValue: formatPercent,
      naReason:
        s.utilization === null
          ? t('productionKpi.na.noMachinesInScope')
          : s.utilization.value === null
            ? t('productionKpi.na.noCapacity')
            : null,
      note: null,
      higherIsBetter: true,
      icon: 'mdi mdi-cog-outline',
    },
    {
      key: 'firstPassYield',
      label: t('productionKpi.tiles.firstPassYield'),
      definition: t('productionKpi.definitions.firstPassYield'),
      value: s.first_pass_yield.value,
      previousValue: p?.first_pass_yield.value ?? null,
      formatValue: formatPercent,
      naReason: s.first_pass_yield.value === null ? t('productionKpi.na.noCompletions') : null,
      note:
        s.first_pass_yield.value === null
          ? null
          : t('productionKpi.tiles.samplePieces', { count: s.first_pass_yield.denominator }),
      higherIsBetter: true,
      icon: 'mdi mdi-check-decagram-outline',
    },
    {
      key: 'scrapRatio',
      label: t('productionKpi.tiles.scrapRatio'),
      definition: t('productionKpi.definitions.scrapRatio'),
      value: s.scrap_ratio.value,
      previousValue: p?.scrap_ratio.value ?? null,
      formatValue: formatPercent,
      naReason: s.scrap_ratio.value === null ? t('productionKpi.na.noCompletions') : null,
      note:
        s.scrap_ratio.value === null
          ? null
          : t('productionKpi.tiles.samplePieces', { count: s.scrap_ratio.denominator }),
      higherIsBetter: false,
      icon: 'mdi mdi-delete-alert-outline',
    },
    {
      key: 'reworkRatio',
      label: t('productionKpi.tiles.reworkRatio'),
      definition: t('productionKpi.definitions.reworkRatio'),
      value: s.rework_ratio.value,
      previousValue: p?.rework_ratio.value ?? null,
      formatValue: formatPercent,
      naReason: s.rework_ratio.value === null ? t('productionKpi.na.noCompletions') : null,
      note:
        s.rework_ratio.value === null
          ? null
          : t('productionKpi.tiles.samplePieces', { count: s.rework_ratio.denominator }),
      higherIsBetter: false,
      icon: 'mdi mdi-wrench-outline',
    },
  ]

  if (s.availability !== null && s.availability.value !== null) {
    list.push({
      key: 'availability',
      label: t('productionKpi.tiles.availability'),
      definition: t('productionKpi.definitions.availability'),
      value: s.availability.value,
      previousValue: p?.availability?.value ?? null,
      formatValue: formatPercent,
      naReason: null,
      note: null,
      higherIsBetter: true,
      icon: 'mdi mdi-power-plug-outline',
    })
  }

  if (s.oee !== null) {
    list.push({
      key: 'oee',
      label: t('productionKpi.tiles.oee'),
      definition: t('productionKpi.definitions.oee'),
      value: s.oee,
      previousValue: p?.oee ?? null,
      formatValue: formatPercent,
      naReason: null,
      note: null,
      higherIsBetter: true,
      icon: 'mdi mdi-gauge',
    })
  }

  return list
})

function reload(): void {
  void store.load()
  void store.loadScrapKpis()
}

// A custom range holds [Date, null] while the second date is being picked,
// which would send a null date_to.
function reloadUnlessIncompleteCustomRange(): void {
  if (periodPreset.value === 'custom' && !customRange.value?.[1]) return
  reload()
}

onMounted(reload)

// The filters are reassigned wholesale, so a shallow watch suffices.
watch(
  [periodPreset, customRange, machineOrPoolKey, selectedProject, selectedCustomer],
  reloadUnlessIncompleteCustomRange,
)
</script>

<template>
  <PageLayout :card="false">
    <template #views>
      <KpiFiltersBar />
    </template>

    <div class="kpi-page">
      <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>

      <AsyncChunkLoading v-if="!summary && loading" />

      <template v-else>
        <section class="kpi-tiles">
          <KpiTile
            v-for="tile in tiles"
            :key="tile.key"
            :label="tile.label"
            :definition="tile.definition"
            :value="tile.value"
            :previous-value="tile.previousValue"
            :format-value="tile.formatValue"
            :na-reason="tile.naReason"
            :note="tile.note"
            :higher-is-better="tile.higherIsBetter"
            :icon="tile.icon"
          />
        </section>

        <section class="kpi-charts">
          <SectionCard :title="t('productionKpi.charts.weeklyTitle')" class="kpi-chart-card">
            <KpiWeeklyChart :points="weekly?.points ?? []" />
          </SectionCard>
          <SectionCard :title="t('productionKpi.charts.utilizationTitle')" class="kpi-chart-card">
            <KpiUtilizationChart :rows="utilization?.rows ?? []" />
          </SectionCard>
        </section>

        <section class="kpi-panels">
          <KpiEstimateAccuracyPanel :rows="estimateAccuracy?.rows ?? []" />
          <KpiWaitingTimePanel :rows="waitingTime?.rows ?? []" />
        </section>

        <section class="kpi-tables">
          <KpiLateLotsTable :rows="lateLots?.rows ?? []" />
          <KpiQualityByItemTable :rows="qualityByItem?.rows ?? []" />
        </section>

        <section class="kpi-scrap">
          <SectionCard :title="t('productionKpi.charts.scrapByReasonTitle')" class="kpi-chart-card">
            <KpiScrapByReasonChart :rows="scrapByReason?.rows ?? []" />
          </SectionCard>
          <KpiRejectedPerSupplierTable :rows="rejectedPerSupplier?.rows ?? []" />
        </section>
      </template>
    </div>
  </PageLayout>
</template>

<style scoped lang="scss">
// A grid so the card rows share the height left under the tiles row and
// the last row reaches the bottom.
.kpi-page {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr);
  gap: var(--space-1);
  height: 100%;
  min-height: 0;
  overflow: auto;
}

// Explicit rows so an error message does not shift the sections down.
.kpi-tiles {
  grid-row: 1;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
  gap: var(--space-1);
}

.kpi-charts,
.kpi-panels,
.kpi-tables,
.kpi-scrap {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(22rem, 1fr));
  gap: var(--space-1);
  min-height: 0;
}

.kpi-charts {
  grid-row: 2;
}

.kpi-panels {
  grid-row: 3;
}

.kpi-tables {
  grid-row: 4;
}

.kpi-scrap {
  grid-row: 5;
}

.kpi-chart-card {
  min-height: 18rem;
}
</style>
