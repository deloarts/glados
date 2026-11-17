<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { AUTO_PLAN_ALGORITHMS, algorithmKey } from '../../utils/autoPlanAlgorithms'
import { useHelpContext } from '@/shared/help'

import type { AutoPlanAlgorithm } from '../../types/scheduleBoardResponse'

// Embedded by the auto-plan handbook doc. The six algorithms stay in the
// locale files rather than the prose because the dialog's picker reads the
// same labels, and duplicating them into markdown would let the two drift.
const { t } = useI18n()

// Read from the handbook context instead of a prop: the doc is the same
// whether it is opened from the dialog (where an algorithm is selected and
// gets highlighted) or read as a standalone page (where none is).
const context = useHelpContext()
const selected = computed(() => context.value.algorithm as AutoPlanAlgorithm | undefined)

const FACTS = ['ordering', 'selection', 'bestFor', 'watchOut'] as const

const algorithms = computed(() =>
  AUTO_PLAN_ALGORITHMS.map((value) => ({
    value,
    label: t(algorithmKey(value, 'label')),
    description: t(algorithmKey(value, 'description')),
    facts: FACTS.map((field) => ({
      field,
      label: t(`productionSchedule.autoPlan.explain.facts.${field}`),
      value: t(algorithmKey(value, field)),
    })),
    current: value === selected.value,
  })),
)
</script>

<template>
  <div class="algorithm-cards">
    <article
      v-for="entry in algorithms"
      :key="entry.value"
      class="algorithm-card"
      :class="{ 'algorithm-card-current': entry.current }"
    >
      <header class="algorithm-card-header">
        <span class="algorithm-card-name">{{ entry.label }}</span>
        <Tag
          v-if="entry.current"
          :value="t('productionSchedule.autoPlan.explain.selected')"
          severity="info"
        />
      </header>
      <p class="algorithm-card-summary">{{ entry.description }}</p>
      <dl class="algorithm-card-facts">
        <template v-for="fact in entry.facts" :key="fact.field">
          <dt>{{ fact.label }}</dt>
          <dd>{{ fact.value }}</dd>
        </template>
      </dl>
    </article>
  </div>
</template>

<style scoped lang="scss">
.algorithm-cards {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.algorithm-card {
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.algorithm-card-current {
  border-color: var(--p-primary-color);
  background: var(--p-highlight-background);
}

.algorithm-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.algorithm-card-name {
  font-weight: 600;
}

.algorithm-card-summary {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.algorithm-card-facts {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: var(--space-1) var(--space-2);
  margin: 0;
  font-size: var(--font-size-sm);
}

.algorithm-card-facts dt {
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.02em;
  color: var(--p-text-muted-color);
  white-space: nowrap;
  padding-top: var(--space-1);
}

.algorithm-card-facts dd {
  margin: 0;
}
</style>
