<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import GroupingChain from '@/core/components/GroupingChain.vue'
import { extractApiError } from '@/core/utils/errors'
import { boundariesFromGroups, computeGroups } from '@/core/utils/grouping'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { regroupMadeItemProcesses } from '../api/regroupMadeItemProcesses'
import { processMethodLabel } from '../utils/madeItemProcessGroups'

import type { MadeItemProcessResponse } from '../types/madeItemsResponse'

const props = defineProps<{
  itemId: number
  processes: MadeItemProcessResponse[]
  readonly?: boolean
  // Per-chip setup and per-piece minutes for a host without the routing
  // table. Also switches the chips to the regular layout.
  showTimes?: boolean
  // Hides this component's own heading and caption.
  hideHint?: boolean
}>()

const emit = defineEmits<{
  updated: [processes: MadeItemProcessResponse[]]
}>()

const { t } = useI18n()
const toast = useAppToast()

const sortedProcesses = computed(() => [...props.processes].sort((a, b) => a.position - b.position))

// An inspection is always its own group, so it renders without a link or
// split control.

// Formatted like the routing table's columns, one line each.
function processTimesMetaLines(p: MadeItemProcessResponse): string[] {
  const setup = p.estimated_setup_minutes ?? getEmptyPlaceholder()
  const perPiece = p.estimated_minutes_per_piece ?? getEmptyPlaceholder()
  return [
    `${t('madeItems.catalogue.processes.setupMinutes')}: ${setup}`,
    `${t('madeItems.catalogue.processes.perPieceMinutes')}: ${perPiece}`,
  ]
}

const chainItems = computed(() =>
  sortedProcesses.value.map((p) => ({
    id: p.id,
    label: processMethodLabel(p),
    sublabel: `#${p.position + 1}`,
    groupable: p.role !== 'inspection',
    icon: p.role === 'inspection' ? 'mdi mdi-check-decagram' : undefined,
    note:
      p.role === 'inspection'
        ? t('madeItems.catalogue.processes.grouping.inspectionStandalone')
        : undefined,
    metaLines: props.showTimes ? processTimesMetaLines(p) : undefined,
  })),
)

// Boundaries around an inspection are saved but not user-toggleable.
const forcedBoundaries = computed<Set<number>>(() => {
  const processes = sortedProcesses.value
  const forced = new Set<number>()
  for (let i = 1; i < processes.length; i++) {
    if (processes[i - 1]!.role === 'inspection' || processes[i]!.role === 'inspection') {
      forced.add(processes[i]!.id)
    }
  }
  return forced
})

// Contiguous runs of equal group_index in position order, as the backend
// stores grouping.
function serverGroups(processes: MadeItemProcessResponse[]): number[][] {
  const result: number[][] = []
  let prevGroupIndex: number | null = null
  for (const process of processes) {
    if (prevGroupIndex === null || process.group_index !== prevGroupIndex) {
      result.push([])
    }
    result[result.length - 1]!.push(process.id)
    prevGroupIndex = process.group_index
  }
  return result
}

// Process ids (other than the first process) that begin a new group.
const boundaries = ref<Set<number>>(new Set())
const saving = ref(false)

function initBoundaries(): void {
  const next = boundariesFromGroups(serverGroups(sortedProcesses.value))
  for (const id of forcedBoundaries.value) next.add(id)
  boundaries.value = next
}

watch(() => props.processes, initBoundaries, { immediate: true })

const groups = computed<number[][]>(() =>
  computeGroups(
    sortedProcesses.value.map((p) => p.id),
    boundaries.value,
  ),
)

const isDirty = computed<boolean>(
  () => JSON.stringify(serverGroups(sortedProcesses.value)) !== JSON.stringify(groups.value),
)

async function save(): Promise<void> {
  saving.value = true
  try {
    const updated = await regroupMadeItemProcesses(props.itemId, groups.value)
    emit('updated', updated)
    toast.success(t('madeItems.catalogue.processes.grouping.saved'))
  } catch (e) {
    toast.error(t('madeItems.catalogue.processes.grouping.saveError'), extractApiError(e) ?? undefined)
  } finally {
    saving.value = false
  }
}

function reset(): void {
  initBoundaries()
}

defineExpose({ save, reset, isDirty, saving })
</script>

<template>
  <div class="grouping">
    <div v-if="!hideHint" class="grouping-header">
      <span class="grouping-title">{{ t('madeItems.catalogue.processes.grouping.title') }}</span>
    </div>

    <div v-if="sortedProcesses.length === 0" class="grouping-empty">
      {{ t('madeItems.catalogue.processes.grouping.empty') }}
    </div>
    <GroupingChain
      v-else
      v-model:boundaries="boundaries"
      :items="chainItems"
      :readonly="readonly"
      :chip-layout="showTimes ? 'regular' : 'compact'"
    />

    <div v-if="!hideHint" class="grouping-summary">
      {{ t('madeItems.catalogue.processes.grouping.groupCount', { count: groups.length }) }}
    </div>
  </div>
</template>

<style scoped lang="scss">
.grouping {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.grouping-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.grouping-title {
  font-size: var(--font-size-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--p-text-muted-color);
  flex: 1;
}

.grouping-empty {
  padding: var(--space-3) 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.grouping-summary {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}
</style>
