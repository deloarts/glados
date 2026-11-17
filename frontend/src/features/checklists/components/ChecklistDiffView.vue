<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { ChecklistDiff, ItemChange } from '../utils/diff'
import { itemPosition, itemTextKey, sectionTitleKey } from '../utils/definitions'
import type { ChecklistDefinition } from '../utils/types'

/**
 * The differences between two revisions of a checklist: header fields that
 * changed, then every item with a different answer or remark, grouped by
 * section in checklist order. Answers to items the type no longer has come
 * last, under their stored id.
 */

const props = defineProps<{
  definition: ChecklistDefinition
  diff: ChecklistDiff
  beforeLabel: string
  afterLabel: string
}>()

const { t } = useI18n()

const ANSWER_SEVERITY: Record<string, 'secondary' | 'success' | 'danger' | 'warn'> = {
  na: 'secondary',
  yes: 'success',
  no: 'danger',
  defect: 'warn',
}

interface Group {
  key: string
  title: string
  changes: ItemChange[]
}

const groups = computed<Group[]>(() => {
  const result: Group[] = []
  for (const change of props.diff.items) {
    const sectionKey = change.item?.sectionKey ?? ''
    let group = result[result.length - 1]
    if (!group || group.key !== sectionKey) {
      const section = props.definition.sectionByKey.get(sectionKey)
      group = {
        key: sectionKey,
        title: section
          ? `${section.number} ${t(sectionTitleKey(props.definition.type, section.key))}`
          : t('checklists.diff.removedItems'),
        changes: [],
      }
      result.push(group)
    }
    group.changes.push(change)
  }
  return result
})

function answerLabel(answer: string | null): string {
  return answer === null ? t('checklists.diff.unanswered') : t(`checklists.answers.${answer}`)
}

function itemText(change: ItemChange): string {
  return change.item ? t(itemTextKey(props.definition.type, change.item)) : change.id
}

function position(change: ItemChange): string {
  return change.item ? itemPosition(props.definition, change.item) : ''
}

function headerValue(field: string, value: string): string {
  if (value === '') return '–'
  if (field === 'legalBasis' && (value === 'directive' || value === 'regulation')) {
    return t(`checklists.legalBases.${value}`)
  }
  return value
}

const empty = computed(() => props.diff.header.length === 0 && props.diff.items.length === 0)
</script>

<template>
  <div class="cld" data-testid="cl-diff">
    <p v-if="empty" class="cld-empty" data-testid="cl-diff-empty">{{ t('checklists.diff.none') }}</p>

    <section v-if="diff.header.length" class="cld-block">
      <h3 class="cld-heading">{{ t('checklists.diff.header') }}</h3>
      <table class="cld-table">
        <thead>
          <tr>
            <th>{{ t('checklists.diff.field') }}</th>
            <th>{{ beforeLabel }}</th>
            <th>{{ afterLabel }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="change in diff.header" :key="change.field" :data-testid="`cl-diff-header-${change.field}`">
            <td class="cld-field">{{ t(`checklists.diff.fields.${change.field}`) }}</td>
            <td class="cld-before">{{ headerValue(change.field, change.before) }}</td>
            <td class="cld-after">{{ headerValue(change.field, change.after) }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section v-for="group in groups" :key="group.key" class="cld-block">
      <h3 class="cld-heading">{{ group.title }}</h3>
      <div v-for="change in group.changes" :key="change.id" class="cld-item" :data-testid="`cl-diff-item-${change.id}`">
        <span class="cld-position">{{ position(change) }}</span>
        <div class="cld-body">
          <p class="cld-text">{{ itemText(change) }}</p>
          <div class="cld-answers">
            <Tag
              :value="answerLabel(change.before.answer)"
              :severity="change.before.answer ? ANSWER_SEVERITY[change.before.answer] : 'secondary'"
              class="cld-tag"
              :class="{ 'cld-tag--empty': change.before.answer === null }"
            />
            <i class="mdi mdi-arrow-right cld-arrow" aria-hidden="true" />
            <Tag
              :value="answerLabel(change.after.answer)"
              :severity="change.after.answer ? ANSWER_SEVERITY[change.after.answer] : 'secondary'"
              class="cld-tag"
              :class="{ 'cld-tag--empty': change.after.answer === null }"
            />
          </div>
          <dl v-if="change.remarkChanged" class="cld-remarks">
            <dt>{{ beforeLabel }}</dt>
            <dd class="cld-before">{{ change.before.remark || '–' }}</dd>
            <dt>{{ afterLabel }}</dt>
            <dd class="cld-after">{{ change.after.remark || '–' }}</dd>
          </dl>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped lang="scss">
.cld {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.cld-empty {
  margin: 0;
  padding: var(--space-4);
  text-align: center;
  color: var(--p-text-muted-color);
}

.cld-block {
  padding: var(--space-3) var(--space-4);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  break-inside: avoid;
}

.cld-heading {
  margin: 0 0 var(--space-2);
  font-size: var(--font-size-md);
  font-weight: 600;
}

.cld-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);

  th,
  td {
    padding: var(--space-1) var(--space-2);
    text-align: left;
    vertical-align: top;
    border-top: 1px solid var(--p-content-border-color);
  }

  th {
    font-weight: 600;
    color: var(--p-text-muted-color);
    border-top: 0;
  }
}

.cld-field {
  font-weight: 600;
}

.cld-before {
  color: var(--p-text-muted-color);
  text-decoration: line-through;
  white-space: pre-wrap;
}

.cld-after {
  white-space: pre-wrap;
}

.cld-item {
  display: grid;
  grid-template-columns: 4rem minmax(0, 1fr);
  gap: var(--space-3);
  padding: var(--space-2) 0;
  border-top: 1px solid var(--p-content-border-color);
  break-inside: avoid;
}

.cld-position {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--p-text-muted-color);
}

.cld-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.cld-text {
  margin: 0;
}

.cld-answers {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.cld-tag--empty {
  opacity: 0.6;
}

.cld-arrow {
  color: var(--p-text-muted-color);
}

.cld-remarks {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--space-1) var(--space-3);
  margin: 0;
  font-size: var(--font-size-sm);

  dt {
    font-weight: 600;
  }

  dd {
    margin: 0;
  }
}
</style>
