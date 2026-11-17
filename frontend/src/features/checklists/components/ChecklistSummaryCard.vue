<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { itemTextKey } from '../utils/definitions'
import type { AnswerCounts, Problem, Verdict } from '../utils/evaluation'
import { ANSWERS } from '../utils/types'
import type { ChecklistDefinition } from '../utils/types'

const props = defineProps<{
  definition: ChecklistDefinition
  counts: AnswerCounts
  completion: number
  verdict: Verdict
  problems: readonly Problem[]
}>()

const emit = defineEmits<{
  select: [id: string]
}>()

const { t } = useI18n()

const rows = computed(() => [
  ...ANSWERS.map((answer) => ({ key: answer, label: t(`checklists.answers.${answer}`), value: props.counts[answer] })),
  { key: 'open', label: t('checklists.summaryCard.open'), value: props.counts.open },
])

function problemText(id: string): string {
  const item = props.definition.itemById.get(id)
  return item ? t(itemTextKey(props.definition.type, item)) : id
}
</script>

<template>
  <aside class="clsum" data-testid="cl-summary">
    <h3 class="clsum-title">{{ t('checklists.summaryCard.title') }}</h3>
    <div class="clsum-verdict" :class="`clsum-verdict--${verdict}`">
      <span class="clsum-verdict-label" data-testid="cl-verdict">{{ t(`checklists.verdicts.${verdict}`) }}</span>
      <small class="clsum-verdict-hint">{{ t(`checklists.verdictHints.${verdict}`) }}</small>
    </div>

    <div class="clsum-completion">
      <span data-testid="cl-completion">{{ t('checklists.summaryCard.completion', { percent: completion }) }}</span>
      <span class="clsum-completion-count">{{ counts.answered }}/{{ counts.total }}</span>
    </div>
    <div class="clsum-bar" aria-hidden="true">
      <span class="clsum-bar-fill" :style="{ width: `${completion}%` }" />
    </div>

    <dl class="clsum-counts">
      <div v-for="row in rows" :key="row.key" class="clsum-count" :class="`clsum-count--${row.key}`">
        <dt>{{ row.label }}</dt>
        <dd :data-testid="`cl-count-${row.key}`">{{ row.value }}</dd>
      </div>
    </dl>

    <h4 class="clsum-subtitle">{{ t('checklists.summaryCard.problems') }}</h4>
    <p v-if="problems.length === 0" class="clsum-empty">{{ t('checklists.summaryCard.noProblems') }}</p>
    <ol v-else class="clsum-problems" data-testid="cl-problems">
      <li v-for="problem in problems" :key="problem.id">
        <button type="button" class="clsum-problem" :data-testid="`cl-problem-${problem.id}`" @click="emit('select', problem.id)">
          <span class="clsum-problem-head">
            <span class="clsum-problem-position">{{ problem.position }}</span>
            <span class="clsum-problem-answer" :class="`clsum-problem-answer--${problem.answer}`">
              {{ t(`checklists.answers.${problem.answer}`) }}
            </span>
          </span>
          <span class="clsum-problem-text">{{ problemText(problem.id) }}</span>
          <span v-if="problem.remark" class="clsum-problem-remark">{{ problem.remark }}</span>
        </button>
      </li>
    </ol>
  </aside>
</template>

<style scoped lang="scss">
.clsum {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.clsum-title,
.clsum-subtitle {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
}

.clsum-subtitle {
  font-size: var(--font-size-sm);
}

.clsum-verdict {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  border-left: 4px solid currentcolor;
  background: var(--p-content-hover-background);
  border-radius: var(--p-content-border-radius);

  &--passed {
    color: var(--p-green-500);
  }

  &--open {
    color: var(--p-text-muted-color);
  }

  &--failed {
    color: var(--p-red-500);
  }
}

.clsum-verdict-label {
  font-size: var(--font-size-xl);
  font-weight: 600;
}

.clsum-verdict-hint {
  color: var(--p-text-muted-color);
}

.clsum-completion {
  display: flex;
  justify-content: space-between;
  font-size: var(--font-size-sm);
}

.clsum-completion-count {
  font-variant-numeric: tabular-nums;
  color: var(--p-text-muted-color);
}

.clsum-bar {
  height: 0.35rem;
  background: var(--p-content-border-color);
  border-radius: 1rem;
  overflow: hidden;
}

.clsum-bar-fill {
  display: block;
  height: 100%;
  background: var(--p-primary-color);
}

.clsum-counts {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--space-1);
  margin: 0;
}

.clsum-count {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-1) var(--space-1);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);

  dt {
    font-size: var(--font-size-xs);
    color: var(--p-text-muted-color);
    white-space: nowrap;
  }

  dd {
    margin: 0;
    font-size: var(--font-size-lg);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }

  &--yes dd {
    color: var(--p-green-500);
  }

  &--no dd {
    color: var(--p-red-500);
  }

  &--defect dd {
    color: var(--p-orange-500);
  }
}

.clsum-empty {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.clsum-problems {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin: 0;
  padding: 0;
  list-style: none;
}

.clsum-problem {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  width: 100%;
  padding: var(--space-2) var(--space-2);
  font: inherit;
  text-align: left;
  color: var(--p-text-color);
  background: transparent;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  cursor: pointer;

  &:hover {
    background: var(--p-content-hover-background);
  }

  &:focus-visible {
    outline: 2px solid var(--p-primary-color);
  }
}

.clsum-problem-head {
  display: flex;
  gap: var(--space-2);
  font-size: var(--font-size-xs);
  font-weight: 600;
}

.clsum-problem-position {
  font-variant-numeric: tabular-nums;
}

.clsum-problem-answer {
  &--no {
    color: var(--p-red-500);
  }

  &--defect {
    color: var(--p-orange-500);
  }
}

.clsum-problem-text {
  display: -webkit-box;
  overflow: hidden;
  font-size: var(--font-size-sm);
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
}

.clsum-problem-remark {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  white-space: pre-wrap;
}
</style>
