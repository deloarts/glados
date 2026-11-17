<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { itemDomId, itemHintKey, itemPosition, itemTextKey } from '../utils/definitions'
import { isProblem } from '../utils/evaluation'
import { formatReferences } from '../utils/references'
import { MAX_TEXT_LENGTH } from '../utils/state'
import { ANSWERS } from '../utils/types'
import type { Answer, ChecklistDefinition, ChecklistItem, LegalBasis } from '../utils/types'

const props = defineProps<{
  definition: ChecklistDefinition
  item: ChecklistItem
  answer: Answer | undefined
  remark: string
  legalBasis: LegalBasis
  readOnly?: boolean
  /** Whether the answer or remark differs from the revision before. */
  changed?: boolean
}>()

const emit = defineEmits<{
  answer: [value: Answer | null]
  remark: [value: string]
}>()

const { t } = useI18n()
const translate = (key: string, params?: Record<string, unknown>) => (params ? t(key, params) : t(key))

const type = computed(() => props.definition.type)
const position = computed(() => itemPosition(props.definition, props.item))
const domId = computed(() => itemDomId(props.definition.type, props.item))
const references = computed(() => formatReferences(props.item.refs, props.legalBasis, translate))

const crossReferences = computed(() =>
  props.item.see.flatMap((id) => {
    const target = props.definition.itemById.get(id)
    const section = target && props.definition.sectionByKey.get(target.sectionKey)
    return target && section ? [t('checklists.itemReference', { section: section.number, item: target.number })] : []
  }),
)

// A finding usually needs an explanation, so answering "no" or "defect" opens
// the remark field; an existing remark keeps it open.
const remarkOpen = ref(props.remark !== '')
watch(
  () => props.answer,
  (answer) => {
    if (isProblem(answer)) remarkOpen.value = true
  },
)

function choose(option: Answer) {
  if (props.readOnly) return
  emit('answer', props.answer === option ? null : option)
}
</script>

<template>
  <div
    :id="domId"
    class="cli"
    :class="[`cli--level-${item.level}`, answer ? `cli--${answer}` : 'cli--open', { 'cli--changed': changed }]"
    :data-testid="`cl-item-${item.id}`"
  >
    <span class="cli-number">
      {{ item.number }}
      <span v-if="changed" class="cli-changed" :data-testid="`cl-changed-${item.id}`">{{ t('checklists.changedBadge') }}</span>
    </span>
    <div class="cli-body">
      <p class="cli-text">{{ t(itemTextKey(type, item)) }}</p>
      <p v-if="item.hint" class="cli-hint">{{ t(itemHintKey(type, item)) }}</p>
      <p v-if="references.length > 0" class="cli-meta" data-testid="cl-item-refs">{{ references.join('; ') }}</p>
      <p v-if="crossReferences.length > 0" class="cli-meta">
        {{ t('checklists.see', { items: crossReferences.join('; ') }) }}
      </p>
      <p v-if="item.methods.length > 0" class="cli-meta cli-methods">
        <span>{{ t('checklists.methodsLabel') }}:</span>
        <abbr v-for="method in item.methods" :key="method" :title="t(`checklists.methods.${method}`)">{{ method }}</abbr>
      </p>
      <Textarea
        v-if="remarkOpen && !readOnly"
        :model-value="remark"
        :aria-label="t('checklists.remark')"
        :placeholder="t('checklists.remark')"
        :maxlength="MAX_TEXT_LENGTH"
        rows="1"
        auto-resize
        fluid
        class="cli-remark-input"
        :data-testid="`cl-remark-${item.id}`"
        @update:model-value="emit('remark', $event ?? '')"
      />
      <p v-if="remark !== ''" class="cli-remark" :class="{ 'cli-remark--editing': remarkOpen && !readOnly }">
        <span class="cli-remark-label">{{ t('checklists.remark') }}:</span> {{ remark }}
      </p>
    </div>
    <div class="cli-actions">
      <div class="cli-answers" role="group" :aria-label="t('checklists.answerGroup', { position })">
        <button
          v-for="option in ANSWERS"
          :key="option"
          type="button"
          class="cli-answer"
          :class="`cli-answer--${option}`"
          :aria-pressed="answer === option"
          :disabled="readOnly"
          :title="t(`checklists.answerTitles.${option}`)"
          :data-testid="`cl-answer-${item.id}-${option}`"
          @click="choose(option)"
        >
          {{ t(`checklists.answers.${option}`) }}
        </button>
      </div>
      <button
        v-if="!readOnly"
        type="button"
        class="cli-remark-toggle"
        :aria-expanded="remarkOpen"
        :aria-label="remarkOpen ? t('checklists.removeRemark') : t('checklists.addRemark')"
        :title="remarkOpen ? t('checklists.removeRemark') : t('checklists.addRemark')"
        :data-testid="`cl-remark-toggle-${item.id}`"
        @click="remarkOpen = !remarkOpen"
      >
        <i class="mdi mdi-comment-text-outline" aria-hidden="true" />
      </button>
    </div>
  </div>
</template>

<style scoped lang="scss">
// One requirement: its position, the question with hint, references and
// verification methods, and on the right the four answers. Selected answers
// carry their colour; "no" and "defect" also tint the row so findings stand
// out while scrolling.
.cli {
  display: grid;
  grid-template-columns: 2.75rem minmax(0, 1fr) auto;
  gap: var(--space-1) var(--space-3);
  align-items: start;
  padding: var(--space-2) var(--space-3);
  border-top: 1px solid var(--p-content-border-color);

  &--no,
  &--defect {
    background: color-mix(in srgb, var(--p-red-500) 6%, transparent);
  }

  &--changed {
    box-shadow: inset 3px 0 0 var(--p-primary-color);
  }
}

.cli-changed {
  display: block;
  margin-top: var(--space-1);
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--p-primary-color);
}

.cli--level-1 .cli-number {
  padding-left: var(--space-3);
}

.cli-number {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  color: var(--p-text-muted-color);
  line-height: 1.5;
}

.cli-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.cli-text {
  margin: 0;
  line-height: 1.5;
}

.cli-hint {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
  font-style: italic;
}

.cli-meta {
  margin: 0;
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.cli-methods {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);

  abbr {
    min-width: 1.25rem;
    padding: 0 var(--space-1);
    text-align: center;
    text-decoration: none;
    border: 1px solid var(--p-content-border-color);
    border-radius: var(--p-content-border-radius);
    cursor: help;
  }
}

.cli-remark-input {
  margin-top: var(--space-1);
  font-size: var(--font-size-sm);
}

.cli-remark {
  margin: 0;
  font-size: var(--font-size-sm);
  white-space: pre-wrap;

  // While the field is open it shows the text already.
  &--editing {
    display: none;
  }
}

.cli-remark-label {
  font-weight: 600;
}

.cli-actions {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.cli-answers {
  display: flex;
}

.cli-answer {
  min-width: 3.75rem;
  padding: var(--space-1) var(--space-2);
  font: inherit;
  font-size: var(--font-size-sm);
  color: var(--p-text-color);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  cursor: pointer;

  & + & {
    margin-left: -1px;
  }

  &:first-child {
    border-radius: var(--p-content-border-radius) 0 0 var(--p-content-border-radius);
  }

  &:last-child {
    border-radius: 0 var(--p-content-border-radius) var(--p-content-border-radius) 0;
  }

  &:hover:not(:disabled) {
    background: var(--p-content-hover-background);
  }

  &:disabled {
    cursor: default;
  }

  &:disabled:not([aria-pressed='true']) {
    opacity: 0.55;
  }

  &:focus-visible {
    position: relative;
    z-index: 1;
    outline: 2px solid var(--p-primary-color);
    outline-offset: 1px;
  }

  &[aria-pressed='true'] {
    position: relative;
    font-weight: 600;
    color: var(--p-primary-contrast-color);
  }

  &--na[aria-pressed='true'] {
    background: var(--p-text-muted-color);
    border-color: var(--p-text-muted-color);
  }

  &--yes[aria-pressed='true'] {
    background: var(--p-green-500);
    border-color: var(--p-green-500);
  }

  &--no[aria-pressed='true'] {
    background: var(--p-red-500);
    border-color: var(--p-red-500);
  }

  &--defect[aria-pressed='true'] {
    background: var(--p-orange-500);
    border-color: var(--p-orange-500);
  }
}

.cli-remark-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  font-size: var(--font-size-lg);
  color: var(--p-text-muted-color);
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--p-content-border-radius);
  cursor: pointer;

  &:hover,
  &[aria-expanded='true'] {
    color: var(--p-primary-color);
    background: var(--p-content-hover-background);
  }

  &:focus-visible {
    outline: 2px solid var(--p-primary-color);
  }
}

@media (max-width: $bp-sm) {
  .cli {
    grid-template-columns: 2.75rem minmax(0, 1fr);
  }

  .cli-actions {
    grid-column: 2;
  }
}
</style>
