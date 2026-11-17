<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatISODate, formatISODateTime } from '@/core/utils/dates'
import InfoBar from '@/shared/components/resource-view/InfoBar.vue'
import type { SequenceDocument } from '../composables/useSequenceDocument'
import type { SequenceTiming } from '../composables/useSequenceTiming'
import { formatDuration } from '../utils/timing'
import type { PassEstimate } from '../utils/timing'
import SequenceStatusTag from './SequenceStatusTag.vue'

/**
 * The identity strip of a sequence, laid out like a checklist's: document
 * number, revision, status, the product it belongs to, its creator and the
 * estimated cycle time: along the picked branches, and the worst case over
 * all of them where that is longer.
 */
const props = defineProps<{ doc: SequenceDocument; timing?: SequenceTiming }>()

const { t } = useI18n()
const sequence = computed(() => props.doc.sequence.value)

function passLabel(pass: PassEstimate): string {
  const time = formatDuration(pass.ms)
  return pass.unestimated === 0 ? time : t('sequences.timing.atLeastUnestimated', { time, n: pass.unestimated }, pass.unestimated)
}

const cycleLabel = computed(() => {
  const cycle = props.timing?.cycle.value
  if (!cycle) return ''
  const picked = t('sequences.timing.cycle', { time: passLabel(cycle.picked) })
  const differs = cycle.worst.ms !== cycle.picked.ms || cycle.worst.unestimated !== cycle.picked.unestimated
  return differs ? `${picked} · ${t('sequences.timing.worst', { time: passLabel(cycle.worst) })}` : picked
})

const cycleTooltip = computed(() => {
  const timing = props.timing
  const id = timing?.variantId.value ?? null
  const variant = id === null ? t('sequences.diagram.commonValues') : (timing?.names.variantName(id) ?? '')
  return t('sequences.timing.cycleTooltip', { variant })
})

const changedTooltip = computed(() => {
  const s = sequence.value
  if (!s?.changed || s.changed === s.created) return ''
  return t('sequences.info.changed', { date: formatISODateTime(s.changed) })
})
</script>

<template>
  <InfoBar>
    <template v-if="sequence">
      <span class="info-title" data-testid="sequence-info-number">{{ sequence.document_number }}</span>
      <span class="info-sep" />
      <Tag
        v-tooltip.bottom="sequence.revision_reason ?? ''"
        :value="t('documents.revision.tag', { revision: sequence.revision })"
        severity="secondary"
      />
      <span class="info-sep" />
      <SequenceStatusTag :sequence="sequence" />
      <Tag v-if="doc.lock.editing.value" :value="t('documents.status.editing')" severity="info" />
      <Tag v-if="doc.dirty.value" :value="t('sequences.status.unsaved')" severity="warn" />
      <span class="info-sep" />
      <span v-tooltip.bottom="t('sequences.info.product')" class="info-muted">
        <i class="mdi mdi-package-variant-closed" aria-hidden="true" />
        <RouterLink
          :to="{ name: 'ProductDetail', params: { id: sequence.product_id, tab: 'sequences' } }"
          class="info-link"
        >
          {{ sequence.product_number }}
        </RouterLink>
      </span>
      <span class="info-sep" />
      <span v-tooltip.bottom="changedTooltip" class="info-muted">
        {{ t('sequences.info.created', { name: sequence.creator_full_name, date: formatISODate(sequence.created) }) }}
      </span>
      <template v-if="cycleLabel">
        <span class="info-sep" />
        <span v-tooltip.bottom="cycleTooltip" class="info-muted" data-testid="sequence-info-cycle">
          <i class="mdi mdi-timer-outline" aria-hidden="true" />
          {{ cycleLabel }}
        </span>
      </template>
    </template>
  </InfoBar>
</template>

<style scoped lang="scss">
.info-title {
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.info-muted {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-lg);
  color: var(--p-text-muted-color);
}

.info-link {
  color: inherit;
}
</style>
