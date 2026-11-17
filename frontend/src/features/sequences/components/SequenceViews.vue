<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { SequenceTiming } from '../composables/useSequenceTiming'
import { SEQUENCE_VIEWS } from '../utils/views'
import type { SequenceView } from '../utils/views'

/**
 * How a sequence is looked at: the variant its values and times are shown
 * for, then the page's views (steps, initial state, displacement-step
 * diagram, GRAFCET), and on the diagram the Time Axis toggle. Without
 * variants the picker stays visible, disabled on the common values.
 */
const props = defineProps<{ timing: SequenceTiming }>()

const view = defineModel<SequenceView>('view', { required: true })

const { t } = useI18n()

// The Select takes null for nothing picked, so the common values, which
// the timing keeps as null, go through a value of their own.
const ALL_VARIANTS = 'all'
const variantOptions = computed(() => [
  { value: ALL_VARIANTS, label: t('sequences.diagram.commonValues') },
  ...props.timing.names.liveVariants.value.map((variant) => ({ value: variant.id, label: variant.name })),
])
const variant = computed<number | typeof ALL_VARIANTS>({
  get: () => props.timing.variantId.value ?? ALL_VARIANTS,
  set: (value) => props.timing.setVariant(value === ALL_VARIANTS ? null : value),
})

const VIEW_ICONS: Record<SequenceView, string> = {
  editor: 'mdi mdi-format-list-numbered',
  initial: 'mdi mdi-home-outline',
  diagram: 'mdi mdi-chart-timeline',
  grafcet: 'mdi mdi-sitemap-outline',
}
</script>

<template>
  <Toolbar data-testid="sequence-views">
    <template #start>
      <Select
        v-model="variant"
        v-tooltip.bottom="t('sequences.diagram.variant')"
        :options="variantOptions"
        option-label="label"
        option-value="value"
        :aria-label="t('sequences.diagram.variant')"
        :disabled="timing.names.liveVariants.value.length === 0"
        class="variant"
        data-testid="sequence-variant"
      />
      <Divider layout="vertical" />
      <Button
        v-for="option in SEQUENCE_VIEWS"
        :key="option"
        :label="t(`sequences.views.${option}`)"
        :icon="VIEW_ICONS[option]"
        severity="contrast"
        :text="view !== option"
        :aria-pressed="view === option"
        :data-testid="`sequence-view-${option}`"
        @click="view = option"
      />
      <template v-if="view === 'diagram'">
        <Divider layout="vertical" />
        <Button
          :label="t('sequences.timing.timeAxis')"
          icon="mdi mdi-timer-outline"
          severity="contrast"
          :text="!timing.timeAxis.value"
          :aria-pressed="timing.timeAxis.value"
          data-testid="sequence-time-axis"
          @click="timing.toggleTimeAxis()"
        />
      </template>
    </template>
  </Toolbar>
</template>

<style scoped lang="scss">
// Wide enough for "All variants" and a typical variant name.
.variant {
  min-width: 14rem;
}
</style>
