<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import GroupingChain from '@/core/components/GroupingChain.vue'
import { boundariesFromGroups, computeGroups } from '@/core/utils/grouping'
import { useFabricationMethodsStore } from '@/features/fabrication-methods'
import { useInspectionMethodsStore } from '@/features/inspection-methods'

import type { MadeItemProcessCreateRequest } from '../types/madeItemsRequest'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { localizeLabel } from '@/shared/utils/localizeLabel'

const processes = defineModel<MadeItemProcessCreateRequest[]>({ default: () => [] })

const { t } = useI18n()
const fabricationMethodsStore = useFabricationMethodsStore()
const inspectionMethodsStore = useInspectionMethodsStore()

function stagedMethodLabel(process: MadeItemProcessCreateRequest): string {
  if (process.role === 'inspection') {
    return (
      localizeLabel(inspectionMethodsStore.getById(process.inspection_method_id)?.name) ||
      getEmptyPlaceholder()
    )
  }
  if (process.fabrication_method_id == null) return getEmptyPlaceholder()
  return (
    localizeLabel(fabricationMethodsStore.getById(process.fabrication_method_id)?.name) ||
    getEmptyPlaceholder()
  )
}

// Identity is the array index. A null group_index starts its own group, as
// the backend normalizes it.
function currentGroups(): number[][] {
  const result: number[][] = []
  let prevRaw: number | null | undefined
  let isFirst = true
  processes.value.forEach((p, index) => {
    const raw = p.group_index
    if (isFirst || raw === null || raw === undefined || raw !== prevRaw) result.push([])
    result[result.length - 1]!.push(index)
    prevRaw = raw
    isFirst = false
  })
  return result
}

// An inspection is always its own group.
const chainItems = computed(() =>
  processes.value.map((p, index) => ({
    id: index,
    label: stagedMethodLabel(p),
    sublabel: `#${index + 1}`,
    groupable: p.role !== 'inspection',
    icon: p.role === 'inspection' ? 'mdi mdi-check-decagram' : undefined,
    note:
      p.role === 'inspection'
        ? t('madeItems.catalogue.processes.grouping.inspectionStandalone')
        : undefined,
  })),
)

// The boundaries around a staged inspection process stay in the model to
// keep it a singleton, but are never rendered as toggles.
const forcedBoundaries = computed<Set<number>>(() => {
  const forced = new Set<number>()
  processes.value.forEach((p, index) => {
    if (index === 0) return
    const prev = processes.value[index - 1]!
    if (prev.role === 'inspection' || p.role === 'inspection') forced.add(index)
  })
  return forced
})

const boundaries = computed<Set<number>>({
  get: () => {
    const next = boundariesFromGroups(currentGroups())
    for (const id of forcedBoundaries.value) next.add(id)
    return next
  },
  set: (next) => {
    const groups = computeGroups(
      processes.value.map((_, index) => index),
      next,
    )
    const groupIndexByPosition = new Map<number, number>()
    groups.forEach((group, groupIndex) => {
      for (const position of group) groupIndexByPosition.set(position, groupIndex)
    })
    processes.value = processes.value.map((p, index) => ({
      ...p,
      group_index: groupIndexByPosition.get(index) ?? index,
    }))
  },
})
</script>

<template>
  <div class="grouping">
    <span class="grouping-title">{{ t('madeItems.catalogue.processes.grouping.title') }}</span>

    <div v-if="processes.length === 0" class="grouping-empty">
      {{ t('madeItems.catalogue.processes.grouping.empty') }}
    </div>
    <GroupingChain v-else v-model:boundaries="boundaries" :items="chainItems" />
  </div>
</template>

<style scoped lang="scss">
.grouping {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.grouping-title {
  font-size: var(--font-size-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--p-text-muted-color);
}

.grouping-empty {
  padding: var(--space-3) 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
