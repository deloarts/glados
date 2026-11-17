<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import PanelLoading from './PanelLoading.vue'

import { severityColorVar } from '../utils/severityColorVar'
import type { StatusCounts } from '../composables/useDashboardSummary'
import { DEMAND_STATUS_SEVERITY } from '@/core/utils/demandStatus'

// How many demands of each kind hold each status, over the whole lists.
const props = defineProps<{
  madeCounts: StatusCounts
  boughtCounts: StatusCounts
  sourceCounts: StatusCounts
  loading: boolean
}>()

const { t } = useI18n()

// Terminal states stay out of the bar, which shows what is still moving;
// their counts show as trailing text.
const PIPELINE_STATUSES = ['open', 'allocated', 'ordered'] as const

interface PipelineRow {
  label: string
  segments: { status: string; count: number }[]
  total: number
  fulfilledCount: number
  canceledCount: number
}

function buildRow(label: string, counts: StatusCounts): PipelineRow {
  const segments = PIPELINE_STATUSES.map((status) => ({ status, count: counts[status] ?? 0 }))
  return {
    label,
    segments,
    total: segments.reduce((sum, s) => sum + s.count, 0),
    fulfilledCount: counts.fulfilled ?? 0,
    canceledCount: counts.canceled ?? 0,
  }
}

const rows = computed<PipelineRow[]>(() => [
  buildRow(t('dashboard.demandPipeline.made'), props.madeCounts),
  buildRow(t('dashboard.demandPipeline.bought'), props.boughtCounts),
  buildRow(t('dashboard.demandPipeline.source'), props.sourceCounts),
])

// Reuses the status labels of the demand features.
function statusLabel(status: string): string {
  return t(`madeItems.demands.status.${status}`)
}

// Made, bought and source demands share these severities.
const legendMap: Record<string, string> = DEMAND_STATUS_SEVERITY
</script>

<template>
  <div class="card demand-pipeline-panel">
    <div class="panel-title">
      <i class="mdi mdi-swap-horizontal" aria-hidden="true" />
      <span>{{ t('dashboard.demandPipeline.title') }}</span>
    </div>

    <PanelLoading v-if="loading && rows.every((r) => r.total === 0)" class="panel-loading" />

    <template v-else>
      <div v-for="row in rows" :key="row.label" class="pipeline-row">
        <div class="pipeline-row-header">
          <span>{{ row.label }}</span>
          <span class="pipeline-row-terminal">
            {{ t('dashboard.demandPipeline.fulfilled', { count: row.fulfilledCount }) }}
          </span>
        </div>
        <div class="pipeline-bar">
          <template v-if="row.total > 0">
            <div
              v-for="segment in row.segments.filter((s) => s.count > 0)"
              :key="segment.status"
              class="pipeline-segment"
              :style="{
                flexGrow: segment.count,
                background: severityColorVar(legendMap[segment.status] ?? 'secondary'),
              }"
              :title="`${statusLabel(segment.status)}: ${segment.count}`"
            />
          </template>
          <div v-else class="pipeline-bar-empty" />
        </div>
      </div>

      <div class="pipeline-legend">
        <span v-for="status in PIPELINE_STATUSES" :key="status" class="pipeline-legend-item">
          <span
            class="pipeline-legend-dot"
            :style="{ background: severityColorVar(legendMap[status] ?? 'secondary') }"
          />
          {{ statusLabel(status) }}
        </span>
      </div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.demand-pipeline-panel {
  gap: var(--space-4);
}

.panel-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.panel-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-5) 0;
  flex: 1 1 auto;
}

.pipeline-row {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.pipeline-row-header {
  display: flex;
  justify-content: space-between;
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.pipeline-row-terminal {
  font-weight: 400;
  color: var(--p-text-muted-color);
}

.pipeline-bar {
  display: flex;
  height: 10px;
  border-radius: 999px;
  overflow: hidden;
  gap: var(--space-1);
  background: var(--p-surface-200);
}

.p-dark .pipeline-bar {
  background: var(--p-surface-700);
}

.pipeline-segment {
  min-width: 4px;
  border-radius: 2px;
}

.pipeline-bar-empty {
  flex: 1 1 auto;
}

.pipeline-legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.pipeline-legend-item {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}

.pipeline-legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
</style>
