<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { sectionTitleKey } from '../utils/definitions'
import { countAnswers, isProblem } from '../utils/evaluation'
import type { Answer, ChecklistDefinition, ChecklistItem as Item, ChecklistSection, LegalBasis } from '../utils/types'
import ChecklistItem from './ChecklistItem.vue'

export type ChecklistFilter = 'all' | 'unanswered' | 'problems' | 'changes'

const props = defineProps<{
  definition: ChecklistDefinition
  section: ChecklistSection
  answers: Readonly<Record<string, Answer>>
  remarks: Readonly<Record<string, string>>
  legalBasis: LegalBasis
  expanded: boolean
  filter: ChecklistFilter
  readOnly?: boolean
  /** Items whose answer or remark differs from the revision before. */
  changedIds?: ReadonlySet<string> | null
}>()

const emit = defineEmits<{
  toggle: []
  answer: [id: string, value: Answer | null]
  remark: [id: string, value: string]
}>()

const { t } = useI18n()

const counts = computed(() => countAnswers(props.section.items, props.answers))
const findings = computed(() => counts.value.no + counts.value.defect)
const changedCount = computed(() => props.section.items.filter((item) => props.changedIds?.has(item.id)).length)
const percent = computed(() => (counts.value.total === 0 ? 0 : (counts.value.answered / counts.value.total) * 100))
const bodyId = computed(() => `checklist-${props.definition.type}-section-${props.section.key}`)

function matches(item: Item): boolean {
  const answer = props.answers[item.id]
  if (props.filter === 'unanswered') return answer === undefined
  if (props.filter === 'problems') return isProblem(answer)
  if (props.filter === 'changes') return props.changedIds?.has(item.id) === true
  return true
}
</script>

<template>
  <section class="cls" :class="{ 'cls--open': expanded }" :data-testid="`cl-section-${section.key}`">
    <button
      type="button"
      class="cls-header"
      :aria-expanded="expanded"
      :aria-controls="bodyId"
      :data-testid="`cl-section-toggle-${section.key}`"
      @click="emit('toggle')"
    >
      <i class="mdi cls-chevron" :class="expanded ? 'mdi-chevron-down' : 'mdi-chevron-right'" aria-hidden="true" />
      <span class="cls-number">{{ section.number }}</span>
      <span class="cls-title">{{ t(sectionTitleKey(definition.type, section.key)) }}</span>
      <span v-if="changedCount > 0" class="cls-changed">{{ t('checklists.sectionChanges', { count: changedCount }) }}</span>
      <span v-if="findings > 0" class="cls-findings">{{ t('checklists.sectionProblems', { count: findings }) }}</span>
      <span class="cls-progress" :data-testid="`cl-section-progress-${section.key}`">
        {{ t('checklists.sectionProgress', { answered: counts.answered, total: counts.total }) }}
      </span>
      <span class="cls-bar" aria-hidden="true">
        <span class="cls-bar-fill" :class="{ 'cls-bar-fill--done': counts.open === 0 }" :style="{ width: `${percent}%` }" />
      </span>
    </button>
    <div v-show="expanded" :id="bodyId" class="cls-body">
      <ChecklistItem
        v-for="item in section.items"
        v-show="matches(item)"
        :key="item.id"
        :definition="definition"
        :item="item"
        :answer="answers[item.id]"
        :remark="remarks[item.id] ?? ''"
        :legal-basis="legalBasis"
        :read-only="readOnly"
        :changed="changedIds?.has(item.id) === true"
        @answer="emit('answer', item.id, $event)"
        @remark="emit('remark', item.id, $event)"
      />
    </div>
  </section>
</template>

<style scoped lang="scss">
.cls {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  overflow: hidden;
}

.cls-header {
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr) auto auto auto;
  align-items: center;
  gap: var(--space-1) var(--space-2);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  font: inherit;
  text-align: left;
  color: var(--p-text-color);
  background: transparent;
  border: 0;
  cursor: pointer;

  &:hover {
    background: var(--p-content-hover-background);
  }

  &:focus-visible {
    outline: 2px solid var(--p-primary-color);
    outline-offset: -2px;
  }
}

.cls-chevron {
  font-size: var(--font-size-lg);
  color: var(--p-text-muted-color);
}

.cls-number {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.cls-title {
  font-weight: 600;
}

.cls-changed {
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--p-primary-color);
}

.cls-findings {
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--p-red-500);
}

.cls-progress {
  font-size: var(--font-size-xs);
  font-variant-numeric: tabular-nums;
  color: var(--p-text-muted-color);
  white-space: nowrap;
}

.cls-bar {
  grid-column: 2 / -1;
  height: 0.2rem;
  background: var(--p-content-border-color);
  border-radius: 1rem;
  overflow: hidden;
}

.cls-bar-fill {
  display: block;
  height: 100%;
  background: var(--p-primary-color);
  transition: width 0.2s ease;

  &--done {
    background: var(--p-green-500);
  }
}

@media (max-width: $bp-sm) {
  .cls-header {
    grid-template-columns: auto auto minmax(0, 1fr);
  }

  .cls-changed,
  .cls-findings,
  .cls-progress {
    grid-column: 3;
  }
}
</style>
