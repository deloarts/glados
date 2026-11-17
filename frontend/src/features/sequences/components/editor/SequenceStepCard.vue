<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { SequenceAction, SequenceStep, SequenceTransition } from '../../types/sequence'
import { TARGET_END, TARGET_NEXT } from '../../types/sequence'
import { useSequenceEditor } from '../../composables/sequenceEditorContext'
import { newAction, newTransition } from '../../utils/factories'
import { arrivalSuggestions } from '../../utils/suggestions'
import { formatDuration } from '../../utils/timing'
import type { StepProblems } from '../../utils/validation'
import ConditionEditor from './ConditionEditor.vue'
import SequenceActionRow from './SequenceActionRow.vue'
import VariantValueInput from './VariantValueInput.vue'

/**
 * One step: its number, description and optional timeout, the actions that
 * start together when it becomes active, and the transitions that leave it.
 * One transition to the next step is the plain case; one to an earlier step
 * makes a loop, and several with conditions make an alternative branch.
 * Each transition is offered the positions the step moves its devices to
 * as conditions. Its estimated duration is shown beside the number, for the branch the
 * cycle time counts, which the engineer may pick among the alternatives.
 * Read-only, the step reads as text: its description, the timeout and the
 * expected duration where set, and each transition's target.
 */
const props = defineProps<{
  number: number
  isFirst: boolean
  isLast: boolean
  problems?: StepProblems
}>()

const step = defineModel<SequenceStep>({ required: true })
const emit = defineEmits<{ move: [by: -1 | 1]; insertAfter: []; remove: [] }>()

const { t } = useI18n()
const { readonly, stepOptions, timing } = useSequenceEditor()

const estimate = computed(() => timing.steps.value.get(step.value.key) ?? null)
const estimateLabel = computed(() => {
  const e = estimate.value
  if (!e) return ''
  if (!e.estimated && e.ms === 0) return '?'
  return e.estimated ? formatDuration(e.ms) : t('sequences.timing.atLeast', { time: formatDuration(e.ms) })
})
const picked = computed(() => timing.pickedTransition(step.value.key))

const actions = computed(() => step.value.actions ?? [])
const transitions = computed(() => step.value.transitions ?? [])

const targetOptions = computed(() => [
  ...(props.isLast ? [] : [{ key: TARGET_NEXT, label: t('sequences.editor.targets.next') }]),
  ...stepOptions.value,
  { key: TARGET_END, label: t('sequences.editor.targets.end') },
])

function targetLabel(target: string | null | undefined): string {
  const key = target ?? TARGET_NEXT
  return targetOptions.value.find((option) => option.key === key)?.label ?? key
}

function patch(next: Partial<SequenceStep>): void {
  step.value = { ...step.value, ...next }
}

function setAction(index: number, action: SequenceAction): void {
  patch({ actions: actions.value.map((a, i) => (i === index ? action : a)) })
}

function removeAction(index: number): void {
  patch({ actions: actions.value.filter((_, i) => i !== index) })
}

function setTransition(index: number, transition: SequenceTransition): void {
  patch({ transitions: transitions.value.map((tr, i) => (i === index ? transition : tr)) })
}

function removeTransition(index: number): void {
  patch({ transitions: transitions.value.filter((_, i) => i !== index) })
}

function addTransition(): void {
  patch({ transitions: [...transitions.value, newTransition(props.isLast ? TARGET_END : TARGET_NEXT)] })
}
</script>

<template>
  <section class="step" :class="{ readonly, 'has-errors': problems?.errors.length }" :data-testid="`sequence-step-${number}`">
    <header class="step-header">
      <span class="step-number" :aria-label="t('sequences.editor.stepNumber', { number })">{{ number }}</span>
      <Tag
        v-if="estimate"
        v-tooltip.bottom="estimate.estimated ? t('sequences.timing.stepTooltip') : t('sequences.timing.unestimatedTooltip')"
        :value="estimateLabel"
        :severity="estimate.estimated ? 'secondary' : 'warn'"
        icon="mdi mdi-timer-outline"
        data-testid="sequence-step-duration"
      />
      <template v-if="readonly">
        <span class="step-description-text" data-testid="sequence-step-description">{{ step.description }}</span>
        <span v-if="step.timeout_ms" class="header-fact">
          <span class="field-label">{{ t('sequences.editor.timeout') }}</span>
          <span>{{ step.timeout_ms }} ms</span>
        </span>
        <span
          v-if="step.expected_duration_ms"
          v-tooltip.bottom="t('sequences.timing.expectedHint')"
          class="header-fact"
          data-testid="sequence-step-expected"
        >
          <span class="field-label">{{ t('sequences.timing.expected') }}</span>
          <VariantValueInput :model-value="step.expected_duration_ms" unit="ms" />
        </span>
      </template>
      <template v-else>
        <InputText
          :model-value="step.description ?? ''"
          :placeholder="t('sequences.editor.stepDescription')"
          maxlength="500"
          size="small"
          fluid
          class="step-description"
          data-testid="sequence-step-description"
          @update:model-value="(description) => patch({ description: description || null })"
        />
        <div class="header-field timeout">
          <label :for="`timeout-${step.key}`" class="field-label">{{ t('sequences.editor.timeout') }}</label>
          <InputNumber
            :model-value="step.timeout_ms ?? null"
            :input-id="`timeout-${step.key}`"
            :min="1"
            suffix=" ms"
            :placeholder="t('sequences.editor.noTimeout')"
            size="small"
            @update:model-value="(value: number | null) => patch({ timeout_ms: value })"
          />
        </div>
        <div v-tooltip.bottom="t('sequences.timing.expectedHint')" class="header-field expected">
          <label :for="`expected-${step.key}`" class="field-label">{{ t('sequences.timing.expected') }}</label>
          <VariantValueInput
            :model-value="step.expected_duration_ms ?? null"
            :input-id="`expected-${step.key}`"
            :min="0"
            unit="ms"
            data-testid="sequence-step-expected"
            @update:model-value="(value) => patch({ expected_duration_ms: value })"
          />
        </div>
        <div class="step-buttons">
          <Button
            v-tooltip.bottom="t('sequences.editor.moveUp')"
            :aria-label="t('sequences.editor.moveUp')"
            icon="mdi mdi-arrow-up"
            severity="secondary"
            text
            size="small"
            :disabled="isFirst"
            @click="emit('move', -1)"
          />
          <Button
            v-tooltip.bottom="t('sequences.editor.moveDown')"
            :aria-label="t('sequences.editor.moveDown')"
            icon="mdi mdi-arrow-down"
            severity="secondary"
            text
            size="small"
            :disabled="isLast"
            @click="emit('move', 1)"
          />
          <Button
            v-tooltip.bottom="t('sequences.editor.insertAfter')"
            :aria-label="t('sequences.editor.insertAfter')"
            icon="mdi mdi-table-row-plus-after"
            severity="secondary"
            text
            size="small"
            @click="emit('insertAfter')"
          />
          <Button
            v-tooltip.bottom="t('sequences.editor.removeStep')"
            :aria-label="t('sequences.editor.removeStep')"
            icon="mdi mdi-delete-outline"
            severity="secondary"
            text
            size="small"
            data-testid="sequence-remove-step"
            @click="emit('remove')"
          />
        </div>
      </template>
    </header>

    <div class="block">
      <span class="field-label">{{ t('sequences.editor.actions') }}</span>
      <SequenceActionRow
        v-for="(action, index) in actions"
        :key="action.key"
        :model-value="action"
        :step-key="step.key"
        @update:model-value="(next) => setAction(index, next)"
        @remove="removeAction(index)"
      />
      <span v-if="actions.length === 0" class="muted">{{ t('sequences.editor.noActions') }}</span>
      <div v-if="!readonly" class="add-buttons">
        <Button
          :label="t('sequences.editor.addDeviceAction')"
          icon="mdi mdi-plus"
          severity="secondary"
          text
          size="small"
          data-testid="sequence-add-action"
          @click="patch({ actions: [...actions, newAction('device')] })"
        />
        <Button
          :label="t('sequences.editor.addTextAction')"
          icon="mdi mdi-plus"
          severity="secondary"
          text
          size="small"
          @click="patch({ actions: [...actions, newAction('text')] })"
        />
      </div>
    </div>

    <div class="block">
      <span class="field-label">{{ t('sequences.editor.transitions') }}</span>
      <div
        v-for="(transition, index) in transitions"
        :key="transition.key"
        class="transition"
        data-testid="sequence-transition"
      >
        <div class="transition-head">
          <span v-if="transitions.length > 1" class="branch">{{ t('sequences.editor.branch', { n: index + 1 }) }}</span>
          <Button
            v-if="transitions.length > 1"
            v-tooltip.bottom="t('sequences.timing.pickBranch')"
            :aria-label="t('sequences.timing.pickBranch')"
            :aria-pressed="picked === transition.key"
            icon="mdi mdi-timer-outline"
            severity="secondary"
            :text="picked !== transition.key"
            size="small"
            data-testid="sequence-transition-pick"
            @click="timing.pick(step.key, transition.key)"
          />
          <span>{{ t('sequences.editor.goTo') }}</span>
          <span v-if="readonly" class="target-text" data-testid="sequence-transition-target">{{ targetLabel(transition.target) }}</span>
          <Select
            v-else
            :aria-label="t('sequences.editor.goTo')"
            :model-value="transition.target ?? TARGET_NEXT"
            :options="targetOptions"
            option-label="label"
            option-value="key"
            size="small"
            class="target"
            data-testid="sequence-transition-target"
            @update:model-value="(target: string) => setTransition(index, { ...transition, target })"
          />
          <Button
            v-if="!readonly && transitions.length > 1"
            v-tooltip.bottom="t('sequences.editor.removeTransition')"
            :aria-label="t('sequences.editor.removeTransition')"
            icon="mdi mdi-close"
            severity="secondary"
            text
            size="small"
            @click="removeTransition(index)"
          />
        </div>
        <ConditionEditor
          :model-value="transition.condition ?? []"
          :step-key="step.key"
          :add-label="t('sequences.editor.addTerm')"
          :suggestions="readonly ? undefined : arrivalSuggestions(step, transition.condition ?? [])"
          @update:model-value="(condition) => setTransition(index, { ...transition, condition })"
        />
      </div>
      <Button
        v-if="!readonly"
        :label="t('sequences.editor.addBranch')"
        icon="mdi mdi-source-branch"
        severity="secondary"
        text
        size="small"
        class="add-branch"
        data-testid="sequence-add-branch"
        @click="addTransition"
      />
    </div>

    <ul v-if="problems && (problems.errors.length || problems.warnings.length)" class="problems">
      <li v-for="key in problems.errors" :key="key" class="error">
        <i class="mdi mdi-alert-circle-outline" aria-hidden="true" />{{ t(`sequences.problems.${key}`) }}
      </li>
      <li v-for="key in problems.warnings" :key="key" class="warning">
        <i class="mdi mdi-alert-outline" aria-hidden="true" />{{ t(`sequences.problems.${key}`) }}
      </li>
    </ul>
  </section>
</template>

<style scoped lang="scss">
.step {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  background: var(--p-content-background);

  &.readonly .step-header {
    align-items: center;
  }

  &.has-errors {
    border-color: var(--p-red-300);
  }
}

// The number and description line up with the inputs, whose labels sit
// above them.
.step-header {
  display: flex;
  gap: var(--space-2);
  align-items: flex-end;
  flex-wrap: wrap;
}

// A GRAFCET step: a square with its number.
.step-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 2rem;
  height: 2rem;
  border: 2px solid var(--p-text-color);
  font-weight: 600;
}

.step-description-text {
  flex: 1 1 16rem;
  font-weight: 600;
}

.header-fact {
  display: inline-flex;
  gap: var(--space-1);
  align-items: baseline;
  font-size: var(--font-size-sm);
}

.target-text {
  font-weight: 600;
}

.step-description {
  flex: 1 1 16rem;
}

.header-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);

  &.timeout :deep(input) {
    width: 8rem;
  }

  &.expected :deep(input) {
    width: 7rem;
  }
}

.field-label {
  font-weight: 600;
}

.step-buttons {
  display: flex;
}

.block {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.add-buttons {
  display: flex;
  gap: var(--space-1);
}

.transition {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2);
  border-left: 3px solid var(--p-primary-color);
  background: var(--p-content-hover-background);
}

.transition-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
}

.branch {
  font-weight: 600;
}

.target {
  min-width: 10rem;
}

.add-branch {
  align-self: flex-start;
}

.muted {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.problems {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: var(--font-size-sm);

  li {
    display: flex;
    gap: var(--space-1);
    align-items: center;
  }

  .error {
    color: var(--p-red-500);
  }

  .warning {
    color: var(--p-orange-500);
  }
}
</style>
