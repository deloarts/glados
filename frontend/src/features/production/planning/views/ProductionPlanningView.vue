<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useProductionQueueStore } from '../../stores/productionQueueStore'
import { useProductionSchedule } from '../../composables/useProductionSchedule'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { LiveResource } from '@/core/realtime/resources'
import { buildProductionPlanning } from '../../utils/productionPlanningTasks'
import { conflictLabelKey } from '../../utils/productionOrderConflicts'
import type { ScheduleConflict } from '../../types/productionOrdersResponse'
import { scalesForResolution } from '../utils/productionPlanningScales'
import type { GanttResolution } from '../utils/productionPlanningScales'
import ProductionPlanningViews from '../components/ProductionPlanningViews.vue'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import AppGanttChart from '@/shared/components/gantt/AppGanttChart.vue'
import { useMadeItemLabel } from '@/features/made-items'
import type { IColumnConfig } from '@svar-ui/vue-gantt'
import { localizeLabel } from '@/shared/utils/localizeLabel'

const { t } = useI18n()
const { format: madeItemLabel } = useMadeItemLabel()
const { withErrorToast } = useErrorToast()
const store = useProductionQueueStore()
const { lotsById, orderedDateByPositionId, loading: loadingLots } = useProductionSchedule()

const resolution = ref<GanttResolution>('day')
const scales = computed(() => scalesForResolution(resolution.value))

function loadAll() {
  return withErrorToast(() => store.fetchAll(), { summary: t('productionPlanning.loadError') })
}

onMounted(() => {
  void loadAll()
})

useLiveRefresh(
  [LiveResource.PRODUCTION_MACHINES, LiveResource.PRODUCTION_ORDERS, LiveResource.PRODUCTION_LOTS],
  () => loadAll(),
)

const planning = computed(() =>
  buildProductionPlanning({
    machines: store.machines.map((machine) => ({
      id: machine.id,
      internal_name: machine.internal_name,
      fabricationMethods: machine.fabrication_methods.map((method) => localizeLabel(method.name)),
    })),
    orders: store.orders,
    lots: [...lotsById.value.values()],
    orderedDateByPositionId: orderedDateByPositionId.value,
    noAssignmentLabel: t('productionPlanning.noAssignment'),
    externalLabel: t('productionPlanning.externalSteps'),
    dateUnknownSuffix: t('productionPlanning.dateUnknownSuffix'),
    conflictLabel: (conflict) => t(conflictLabelKey(conflict as ScheduleConflict)),
    madeItemLabel,
  }),
)
const tasks = computed(() => planning.value.tasks)
const links = computed(() => planning.value.links)

const columns = computed<IColumnConfig[]>(() => [
  {
    id: 'text',
    header: t('productionPlanning.columns.machineOrOrder'),
    width: 260,
    flexgrow: 1,
    sort: true,
  },
  {
    id: 'status',
    header: t('productionPlanning.columns.status'),
    width: 130,
    align: 'center',
    sort: true,
    getter: (obj) => (obj.status ? t(`productionQueue.status.${obj.status}`) : ''),
  },
  {
    id: 'start',
    header: t('productionPlanning.columns.start'),
    width: 130,
    align: 'center',
    sort: true,
  },
  {
    id: 'duration',
    header: t('productionPlanning.columns.durationDays'),
    width: 130,
    align: 'center',
    sort: true,
  },
])

// The chart is read-only; it reflects the backend scheduler. Reassigning and
// reordering happen on the queue board or the Manage Production panel.
</script>

<template>
  <PageLayout
    data-class="planning-view-data"
    :card="false"
  >
    <template #views>
      <ProductionPlanningViews v-model:resolution="resolution" />
    </template>

    <div class="card">
      <div v-if="!(store.loading || loadingLots) && tasks.length === 0" class="empty-note">
        {{ t('productionPlanning.empty') }}
      </div>
      <AppGanttChart
        v-else
        class="gantt"
        :tasks="tasks"
        :links="links"
        :scales="scales"
        :columns="columns"
        :readonly="true"
      />
    </div>
  </PageLayout>
</template>

<style scoped lang="scss">
:deep(.planning-view-data) {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: visible;
}

.card {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.gantt {
  flex: 1;
  min-height: 0;
}

.empty-note {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

// A conflicted bar is marked with an inset so its size never changes.
:deep(.wx-bar.conflict) {
  box-shadow: inset 0 0 0 2px var(--p-orange-500);
}
</style>
