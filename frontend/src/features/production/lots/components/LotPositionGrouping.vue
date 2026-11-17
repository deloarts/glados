<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import GroupingChain from '@/core/components/GroupingChain.vue'
import { extractApiError } from '@/core/utils/errors'
import { boundariesFromGroups, computeGroups } from '@/core/utils/grouping'
import { useProductionLotDetailStore } from '../stores/productionLotDetailStore'
import { stepMethodLabel } from '../../utils/lotStepDisplay'

import type { LotPositionResponse, LotStepResponse } from '../../types/productionLotsResponse'
import { bySequence, sortedBySequence } from '../../utils/sequence'

const props = defineProps<{
  lotId: number
  steps: LotStepResponse[]
  positions: LotPositionResponse[]
  readonly: boolean
  // Hides the header Reset and Save for hosts with their own footer.
  hideActions?: boolean
  // Staged mode emits a regroup for the host's draft instead of saving.
  staged?: boolean
}>()

const emit = defineEmits<{
  regroup: [groups: number[][]]
}>()

const { t } = useI18n()
const toast = useAppToast()
const detailStore = useProductionLotDetailStore()

const sortedSteps = computed(() => sortedBySequence(props.steps))

// An inspection step is always its own position, so it renders without a
// link or split control.
const chainItems = computed(() =>
  sortedSteps.value.map((step) => ({
    id: step.id,
    label: stepMethodLabel(step),
    sublabel: `#${step.sequence}`,
    groupable: step.role !== 'inspection',
    icon: step.role === 'inspection' ? 'mdi mdi-check-decagram' : undefined,
    note:
      step.role === 'inspection'
        ? t('production.lots.detail.grouping.inspectionStandalone')
        : undefined,
  })),
)

// Boundaries around an inspection step are saved but not user-toggleable.
const forcedBoundaries = computed<Set<number>>(() => {
  const steps = sortedSteps.value
  const forced = new Set<number>()
  for (let i = 1; i < steps.length; i++) {
    if (steps[i - 1]!.role === 'inspection' || steps[i]!.role === 'inspection') {
      forced.add(steps[i]!.id)
    }
  }
  return forced
})

// Step ids (other than the first step) that begin a new position.
const boundaries = ref<Set<number>>(new Set())
const saving = ref(false)

function initBoundaries(): void {
  const orderedPositions = sortedBySequence(props.positions)
  const positionGroups = orderedPositions.map((position) =>
    sortedBySequence(position.steps).map((s) => s.id),
  )
  const next = boundariesFromGroups(positionGroups)
  for (const id of forcedBoundaries.value) next.add(id)
  boundaries.value = next
}

watch(() => props.positions, initBoundaries, { immediate: true })

const groups = computed<number[][]>(() =>
  computeGroups(
    sortedSteps.value.map((s) => s.id),
    boundaries.value,
  ),
)

const isDirty = computed<boolean>(() => {
  const currentGroups = [...props.positions]
    .sort(bySequence)
    .map((p) => sortedBySequence(p.steps).map((s) => s.id))
  return JSON.stringify(currentGroups) !== JSON.stringify(groups.value)
})

// Staged: emitted from the toggle, not a watcher on groups, since groups is
// a fresh array per recompute and re-emitting would churn with the host.
function onBoundariesChange(next: Set<number>): void {
  boundaries.value = next
  if (!props.staged) return
  const nextGroups = computeGroups(
    sortedSteps.value.map((s) => s.id),
    next,
  )
  emit('regroup', nextGroups)
}

async function save(): Promise<void> {
  // Staged: the grouping is written with the rest of the structure on Save.
  if (props.staged) {
    emit('regroup', groups.value)
    return
  }
  saving.value = true
  try {
    await detailStore.regroupPositions(props.lotId, groups.value)
    toast.success(t('production.lots.detail.grouping.saved'))
  } catch (e) {
    toast.error(t('production.lots.detail.grouping.saveError'), extractApiError(e) ?? undefined)
  } finally {
    saving.value = false
  }
}

function reset(): void {
  initBoundaries()
}

defineExpose({ save, reset, isDirty })
</script>

<template>
  <div class="grouping">
    <div class="grouping-header">
      <span class="grouping-title">{{ t('production.lots.detail.grouping.title') }}</span>
      <div v-if="!readonly && !hideActions && !staged" class="grouping-actions compact-buttons">
        <Button
          :label="t('production.lots.detail.grouping.reset')"
          size="small"
          severity="secondary"
          outlined
          :disabled="!isDirty || saving"
          @click="reset"
        />
        <Button
          :label="t('common.save')"
          size="small"
          :loading="saving"
          :disabled="!isDirty"
          @click="save"
        />
      </div>
    </div>

    <div v-if="sortedSteps.length === 0" class="grouping-empty">
      {{ t('production.lots.detail.grouping.empty') }}
    </div>
    <GroupingChain
      v-else
      :boundaries="boundaries"
      :items="chainItems"
      :readonly="readonly"
      @update:boundaries="onBoundariesChange"
    />

    <div class="grouping-summary">
      {{ t('production.lots.detail.grouping.positionCount', { count: groups.length }) }}
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

.grouping-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
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
