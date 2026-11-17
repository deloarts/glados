<script setup lang="ts">
import { computed } from 'vue'
import { Gantt, Willow, WillowDark } from '@svar-ui/vue-gantt'
import type { ITask, ILink, IScaleConfig, IColumnConfig, IApi, IMarker } from '@svar-ui/vue-gantt'
import '@svar-ui/vue-gantt/all.css'
// The themes would link this icon font and Open Sans from SVAR's CDN, so they
// get :fonts="false" below and the icon font comes from the bundle instead.
import '@/assets/fonts/svar/wx-icons.css'
import { storeToRefs } from 'pinia'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { DAY_MS, instantToPickerDate } from '@/core/utils/dates'

const DEFAULT_SCALES: IScaleConfig[] = [
  { unit: 'month', step: 1, format: '%F %Y' },
  { unit: 'week', step: 1, format: '%W' },
]


interface Props {
  tasks: ITask[]
  links?: ILink[]
  scales?: IScaleConfig[]
  columns?: IColumnConfig[] | false
  readonly?: boolean
  // A vertical "today" line is on by default for every consumer of this
  // shared wrapper. Set to false to opt out.
  todayMarker?: boolean
  // Escape hatch for callers that need to react to or veto SVAR's own edit
  // events (drag/move/resize) via api.on/api.intercept. See
  // ProductionPlanningView.vue for the one consumer that uses this today.
  init?: (api: IApi) => void
}

// withDefaults is only safe here for LITERAL defaults (true/false). A
// default expression that references an external identifier (like the
// DEFAULT_SCALES const above) gets hoisted outside setup() by the SFC
// compiler and is rejected, so scales/columns/links use a `?? fallback`
// computed instead. The booleans need withDefaults: an optional
// `boolean`-typed prop that is never passed is auto-defaulted by Vue's
// compiler to `false` (not `undefined`, mirroring native HTML boolean
// attributes), so a `?? true` fallback would never apply and
// `props.todayMarker === false` would hold for callers that never set it.
const props = withDefaults(defineProps<Props>(), {
  readonly: true,
  todayMarker: true,
})

const links = computed(() => props.links ?? [])
const scales = computed(() => props.scales ?? DEFAULT_SCALES)
// The bars sit on the tenant's calendar, so the marker shows the tenant's
// current time on the same axis.
const markers = computed<IMarker[]>(() =>
  props.todayMarker ? [{ start: instantToPickerDate(new Date()) }] : [],
)

// A zero-duration bar (start === end) renders as an invisible sliver.
// Stretch it to a minimum of one day so every row stays visible/clickable.
const tasks = computed(() =>
  props.tasks.map((task) => {
    if (!task.start || !task.end) return task
    if (task.end.getTime() - task.start.getTime() >= DAY_MS) return task
    return { ...task, end: new Date(task.start.getTime() + DAY_MS) }
  }),
)

const { isDarkMode } = storeToRefs(useLayoutStore())
const theme = computed(() => (isDarkMode.value ? WillowDark : Willow))
</script>

<template>
  <div class="gantt-chart">
    <component :is="theme" :fonts="false">
      <Gantt
        :tasks="tasks"
        :links="links"
        :scales="scales"
        :columns="props.columns"
        :readonly="props.readonly"
        :markers="markers"
        :init="props.init"
      />
    </component>
  </div>
</template>

<style scoped>
.gantt-chart {
  height: 100%;
  width: 100%;
}

.gantt-chart :deep(.wx-willow-theme),
.gantt-chart :deep(.wx-willow-dark-theme) {
  height: 100%;
  --wx-font-family: var(--font-body);
  --wx-font-size: var(--font-size-sm);
  --wx-font-size-md: var(--font-size-sm);
}
</style>
