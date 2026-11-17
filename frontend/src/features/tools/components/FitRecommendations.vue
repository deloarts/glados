<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { FIT_RECOMMENDATIONS } from '../utils/fitRecommendations'
import type { FitRecommendation } from '../utils/fitRecommendations'
import type { FitType } from '../utils/iso286/fit'

const props = defineProps<{
  holeCode: string
  shaftCode: string
}>()

const emit = defineEmits<{
  select: [recommendation: FitRecommendation]
}>()

const { t } = useI18n()

type SystemFilter = 'all' | 'hole' | 'shaft'

const system = ref<SystemFilter>('all')
const seriesOneOnly = ref(false)

const systemOptions = computed(() =>
  (['all', 'hole', 'shaft'] as const).map((value) => ({
    value,
    label: t(`tools.fitCalculator.recommendations.systems.${value}`),
  })),
)

const GROUPS: readonly FitType[] = ['clearance', 'transition', 'interference']

const groups = computed(() =>
  GROUPS.map((group) => ({
    group,
    items: FIT_RECOMMENDATIONS.filter(
      (rec) =>
        rec.group === group &&
        (system.value === 'all' || rec.system === system.value || rec.system === 'both') &&
        (!seriesOneOnly.value || rec.series === 1),
    ),
  })).filter((g) => g.items.length > 0),
)

function isActive(rec: FitRecommendation): boolean {
  return rec.hole === props.holeCode && rec.shaft === props.shaftCode
}
</script>

<template>
  <aside class="recs" :aria-label="t('tools.fitCalculator.recommendations.title')">
    <header class="recs-header">
      <h3 class="recs-title">{{ t('tools.fitCalculator.recommendations.title') }}</h3>
      <p class="recs-subtitle">{{ t('tools.fitCalculator.recommendations.subtitle') }}</p>
    </header>

    <SelectButton
      v-model="system"
      :options="systemOptions"
      option-label="label"
      option-value="value"
      :allow-empty="false"
      :aria-label="t('tools.fitCalculator.recommendations.systemFilter')"
      class="recs-systems"
      :pt="{ pcToggleButton: { root: { class: 'recs-system' } } }"
    />
    <label class="recs-series">
      <Checkbox v-model="seriesOneOnly" binary input-id="fit-recs-series-one" />
      <span>{{ t('tools.fitCalculator.recommendations.seriesOneOnly') }}</span>
    </label>

    <div class="recs-list">
      <div v-for="g in groups" :key="g.group" class="recs-group">
        <div class="recs-group-title" :class="`recs-group-title--${g.group}`">
          {{ t(`tools.fitCalculator.recommendations.groups.${g.group}`) }}
          <span class="recs-group-count">{{ g.items.length }}</span>
        </div>
        <button
          v-for="rec in g.items"
          :key="`${rec.hole}/${rec.shaft}`"
          type="button"
          class="recs-item"
          :class="{ 'recs-item--active': isActive(rec) }"
          :aria-pressed="isActive(rec)"
          :data-testid="`fit-rec-${rec.hole}-${rec.shaft}`"
          @click="emit('select', rec)"
        >
          <span class="recs-item-head">
            <span class="recs-item-code">{{ rec.hole }}/{{ rec.shaft }}</span>
            <span class="recs-item-series" :class="{ 'recs-item-series--one': rec.series === 1 }">
              {{ t('tools.fitCalculator.recommendations.series', { series: rec.series }) }}
            </span>
            <span class="recs-item-system">
              {{ t(`tools.fitCalculator.recommendations.systems.${rec.system}`) }}
            </span>
          </span>
          <template v-if="rec.descriptionKey">
            <span class="recs-item-title">{{
              t(`tools.fitCalculator.recommendations.descriptions.${rec.descriptionKey}.title`)
            }}</span>
            <span class="recs-item-use">{{
              t(`tools.fitCalculator.recommendations.descriptions.${rec.descriptionKey}.use`)
            }}</span>
          </template>
        </button>
      </div>
      <p v-if="groups.length === 0" class="recs-empty">
        {{ t('tools.fitCalculator.recommendations.empty') }}
      </p>
    </div>
  </aside>
</template>

<style scoped lang="scss">
.recs {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  min-width: 0;
}

.recs-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.recs-header {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.recs-title {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
}

.recs-subtitle {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.recs-systems {
  display: flex;

  :deep(.recs-system) {
    flex: 1;
  }
}

.recs-series {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  cursor: pointer;
}

.recs-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.recs-group-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding-top: var(--space-1);
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--p-text-muted-color);

  &::before {
    content: '';
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
  }

  &--clearance::before {
    background: var(--p-blue-500);
  }

  &--transition::before {
    background: var(--p-yellow-500);
  }

  &--interference::before {
    background: var(--p-orange-500);
  }
}

.recs-group-count {
  margin-left: auto;
  font-weight: 500;
}

.recs-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-1);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  text-align: left;
  font: inherit;
  color: var(--p-text-color);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  cursor: pointer;

  &:hover {
    background: var(--p-content-hover-background);
  }

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: 1px;
  }

  &--active {
    border-color: var(--p-primary-color);
    background: var(--p-highlight-bg);
  }
}

.recs-item-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
}

.recs-item-code {
  font-weight: 600;
  font-size: var(--font-size-md);
}

.recs-item-series {
  font-size: var(--font-size-xs);
  font-weight: 600;
  padding: var(--space-1) var(--space-2);
  border-radius: 999px;
  background: var(--p-content-hover-background);
  color: var(--p-text-muted-color);

  &--one {
    background: var(--p-primary-color);
    color: var(--p-primary-contrast-color);
  }
}

.recs-item-system {
  margin-left: auto;
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.recs-item-title {
  font-weight: 500;
  font-size: var(--font-size-sm);
}

.recs-item-use {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.recs-empty {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
