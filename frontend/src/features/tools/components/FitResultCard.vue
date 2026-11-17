<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useFitFormat } from '../composables/useFitFormat'
import { fitFigures } from '../utils/iso286/fit'
import type { Fit } from '../utils/iso286/fit'
import { isRecommendedForSize } from '../utils/fitRecommendations'
import type { FitRecommendation } from '../utils/fitRecommendations'

const props = defineProps<{
  fit: Fit | null
  recommendation: FitRecommendation | undefined
  size: number | null
}>()

const { t } = useI18n()
const fmt = useFitFormat()

const SEVERITY = { clearance: 'info', transition: 'warn', interference: 'danger' } as const

const rows = computed(() =>
  props.fit
    ? fitFigures(props.fit).map((figure) => ({
        kind: figure.kind,
        label: t(`tools.fitCalculator.figures.${figure.kind}`),
        um: fmt.amountUm(figure.value),
        mm: fmt.amountMm(figure.value),
      }))
    : [],
)

const sizeHint = computed(() => {
  const rec = props.recommendation
  if (!rec || props.size === null || isRecommendedForSize(rec, props.size)) return ''
  const fit = `${rec.hole}/${rec.shaft}`
  if (rec.maxSize !== undefined) {
    return t('tools.fitCalculator.recommendedSizeHint.maxSize', { fit, size: rec.maxSize })
  }
  return t('tools.fitCalculator.recommendedSizeHint.minSize', { fit, size: rec.minSize ?? 0 })
})
</script>

<template>
  <section class="fit-card" data-testid="fit-result-card">
    <header class="fit-card-header">
      <h3 class="fit-card-title">{{ t('tools.fitCalculator.fit') }}</h3>
      <Tag
        v-if="fit"
        :value="t(`tools.fitCalculator.types.${fit.type}`)"
        :severity="SEVERITY[fit.type]"
        data-testid="fit-type"
      />
    </header>

    <dl v-if="rows.length" class="fit-rows">
      <div v-for="row in rows" :key="row.kind" class="fit-row">
        <dt>{{ row.label }}</dt>
        <dd class="fit-row-um">{{ row.um }}</dd>
        <dd class="fit-row-mm" :data-testid="`fit-${row.kind}`">{{ row.mm }}</dd>
      </div>
    </dl>

    <div v-if="fit && recommendation" class="fit-recommended" data-testid="fit-recommended">
      <span class="fit-recommended-label">
        <i class="mdi mdi-check-decagram-outline" aria-hidden="true" />
        {{ t('tools.fitCalculator.recommended', { series: recommendation.series }) }}
      </span>
      <template v-if="recommendation.descriptionKey">
        <strong>{{
          t(`tools.fitCalculator.recommendations.descriptions.${recommendation.descriptionKey}.title`)
        }}</strong>
        <span>{{
          t(`tools.fitCalculator.recommendations.descriptions.${recommendation.descriptionKey}.use`)
        }}</span>
      </template>
      <span v-if="sizeHint" class="fit-recommended-hint">{{ sizeHint }}</span>
    </div>
    <p v-else-if="fit" class="fit-not-recommended">{{ t('tools.fitCalculator.notRecommended') }}</p>
  </section>
</template>

<style scoped lang="scss">
.fit-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  min-width: 0;
}

.fit-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.fit-card-title {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
}

.fit-rows {
  margin: 0;
  display: flex;
  flex-direction: column;
}

.fit-row {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  border-top: 1px solid var(--p-content-border-color);

  dt {
    flex: 1;
    color: var(--p-text-muted-color);
  }

  dd {
    margin: 0;
    font-variant-numeric: tabular-nums;
  }
}

.fit-row-um {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.fit-row-mm {
  min-width: 6.5rem;
  text-align: right;
  font-weight: 500;
}

.fit-recommended {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--p-content-border-radius);
  background: var(--p-highlight-bg);
}

.fit-recommended-label {
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--p-primary-color);
}

.fit-recommended-hint {
  font-size: var(--font-size-sm);
  color: var(--p-orange-500);
}

.fit-not-recommended {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
