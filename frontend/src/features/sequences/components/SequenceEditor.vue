<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { AutoCompleteCompleteEvent } from 'openvue/autocomplete'

import { useProductDeviceResourcesStore } from '@/features/product-devices'
import EmptyState from '@/shared/components/EmptyState.vue'
import { useLocalizedText } from '@/shared/composables/useLocalizedText'
import { provideSequenceEditor } from '../composables/sequenceEditorContext'
import type { SequenceDocument } from '../composables/useSequenceDocument'
import { useSequenceTiming } from '../composables/useSequenceTiming'
import type { SequenceTiming } from '../composables/useSequenceTiming'
import type { SequenceStep } from '../types/sequence'
import { TARGET_END, TARGET_NEXT } from '../types/sequence'
import { newStep } from '../utils/factories'
import { stepProblems } from '../utils/validation'
import SequenceStepCard from './editor/SequenceStepCard.vue'

/**
 * The name and the steps of a sequence. Steps are numbered by their
 * order; references between them use keys, so moving a step keeps the
 * transitions and conditions that name it. The problems the server would
 * refuse are shown on the step while editing. Read-only, the name and the
 * steps read as text.
 */
const props = defineProps<{ doc: SequenceDocument; timing?: SequenceTiming }>()

const name = defineModel<string>('name', { required: true })
const steps = defineModel<SequenceStep[]>('steps', { required: true })

const { t } = useI18n()
const { localize } = useLocalizedText()
const resources = useProductDeviceResourcesStore()
// The page shares its timing with the info strip and the diagram.
const timing = props.timing ?? useSequenceTiming(props.doc, () => steps.value)
const names = timing.names
const readonly = computed(() => !props.doc.editable.value)

const numbers = computed(() => new Map(steps.value.map((step, index) => [step.key, index + 1])))
const stepOptions = computed(() =>
  steps.value.map((step, index) => ({
    key: step.key,
    label: step.description
      ? t('sequences.editor.stepLabel', { number: index + 1, description: step.description })
      : t('sequences.editor.stepNumber', { number: index + 1 }),
  })),
)

provideSequenceEditor({
  names,
  readonly,
  stepNumber: (key) => numbers.value.get(key) ?? null,
  stepOptions,
  timing,
})

const problems = computed(() =>
  stepProblems(steps.value, {
    takesValue: (deviceId, positionId) => names.position(deviceId, positionId)?.takesValue ?? false,
    liveVariantIds: names.liveVariants.value.map((variant) => variant.id),
    isDriven: (deviceId) => (names.deviceById.value.get(deviceId)?.drivenById ?? null) !== null,
  }),
)

// ── Name proposals ────────────────────────────────────────────────────

const suggestions = ref<string[]>([])
function complete(event: AutoCompleteCompleteEvent): void {
  const query = event.query.trim().toLocaleLowerCase()
  suggestions.value = resources
    .optionsOf('sequence_name')
    .map((option) => localize(option.label))
    .filter((proposal) => proposal.toLocaleLowerCase().includes(query))
}

// ── Steps ─────────────────────────────────────────────────────────────

function setStep(index: number, step: SequenceStep): void {
  steps.value = steps.value.map((s, i) => (i === index ? step : s))
}

// A step that becomes the last one cannot lead to a next step; its
// transitions to one end the sequence instead.
function withoutNextOnLast(list: SequenceStep[]): SequenceStep[] {
  const last = list.at(-1)
  if (!last) return list
  const transitions = (last.transitions ?? []).map((tr) => (tr.target === TARGET_NEXT ? { ...tr, target: TARGET_END } : tr))
  return [...list.slice(0, -1), { ...last, transitions }]
}

// A step that gets a step after it again goes on to it, when its only
// transition simply ended the sequence.
function reopen(step: SequenceStep): SequenceStep {
  const transitions = step.transitions ?? []
  const only = transitions.length === 1 ? transitions[0] : undefined
  if (!only || only.target !== TARGET_END || (only.condition ?? []).length > 0) return step
  return { ...step, transitions: [{ ...only, target: TARGET_NEXT }] }
}

function insertAfter(index: number): void {
  const next = steps.value.map((step, i) => (i === index && index === steps.value.length - 1 ? reopen(step) : step))
  next.splice(index + 1, 0, newStep())
  steps.value = withoutNextOnLast(next)
}

function addStep(): void {
  if (steps.value.length === 0) steps.value = withoutNextOnLast([newStep()])
  else insertAfter(steps.value.length - 1)
}

function move(index: number, by: -1 | 1): void {
  const target = index + by
  if (target < 0 || target >= steps.value.length) return
  const next = [...steps.value]
  const [step] = next.splice(index, 1)
  if (step) next.splice(target, 0, step)
  steps.value = withoutNextOnLast(next)
}

// Conditions and transitions that named the removed step lose that reference.
function remove(index: number): void {
  const removed = steps.value[index]
  if (!removed) return
  const key = removed.key
  const next = steps.value
    .filter((_, i) => i !== index)
    .map((step) => ({
      ...step,
      transitions: (step.transitions ?? []).map((tr) => ({
        ...tr,
        target: tr.target === key ? TARGET_NEXT : tr.target,
        condition: (tr.condition ?? []).map((term) => (term.step_key === key ? { ...term, step_key: null } : term)),
      })),
    }))
  steps.value = withoutNextOnLast(next)
}
</script>

<template>
  <div class="card sequence-editor">
    <div class="editor-body">
      <div v-if="readonly" class="name-field">
        <span class="field-label">{{ t('sequences.fields.flow') }}</span>
        <span class="name-text" data-testid="sequence-name-text">{{ name }}</span>
      </div>
      <div v-else class="name-field">
        <label for="sequence-name" class="field-label">{{ t('sequences.fields.name') }}</label>
        <AutoComplete
          v-model="name"
          input-id="sequence-name"
          :suggestions="suggestions"
          maxlength="200"
          dropdown
          fluid
          data-testid="sequence-name"
          @complete="complete"
        />
      </div>

      <EmptyState v-if="steps.length === 0" :message="t('sequences.editor.noSteps')" icon="mdi mdi-format-list-numbered">
        <Button
          v-if="!readonly"
          :label="t('sequences.editor.addStep')"
          icon="mdi mdi-plus"
          severity="contrast"
          text
          data-testid="sequence-add-step"
          @click="addStep"
        />
      </EmptyState>
      <div v-else class="steps">
        <template v-for="(step, index) in steps" :key="step.key">
          <SequenceStepCard
            :model-value="step"
            :number="index + 1"
            :is-first="index === 0"
            :is-last="index === steps.length - 1"
            :problems="readonly ? undefined : problems.get(step.key)"
            @update:model-value="(next) => setStep(index, next)"
            @move="(by) => move(index, by)"
            @insert-after="insertAfter(index)"
            @remove="remove(index)"
          />
          <!-- Between two steps, a step can be put in where it belongs. -->
          <div v-if="!readonly && index < steps.length - 1" class="insert-gap">
            <Button
              :label="t('sequences.editor.insertStep')"
              icon="mdi mdi-plus"
              severity="secondary"
              text
              size="small"
              class="insert-step"
              data-testid="sequence-insert-step"
              @click="insertAfter(index)"
            />
          </div>
        </template>
        <Button
          v-if="!readonly"
          :label="t('sequences.editor.addStep')"
          icon="mdi mdi-plus"
          severity="secondary"
          text
          size="small"
          class="add-step"
          data-testid="sequence-add-step"
          @click="addStep"
        />
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
// The standard content card; the steps scroll inside it, never the page.
.sequence-editor {
  padding: 0;
}

.editor-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
}

.name-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  max-width: 32rem;
}

.name-text {
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.field-label {
  font-weight: 600;
}

.steps {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.add-step {
  align-self: flex-start;
}

// A line between two steps whose button shows on hover or keyboard focus,
// so the gap stays quiet while reading.
.insert-gap {
  position: relative;
  display: flex;
  justify-content: center;
  height: 1.25rem;
  margin: -0.5rem 0;

  &::before {
    content: '';
    position: absolute;
    top: 50%;
    left: 0;
    right: 0;
    border-top: 1px dashed var(--p-content-border-color);
    opacity: 0;
    transition: opacity 0.15s;
  }

  .insert-step {
    position: relative;
    height: 1.25rem;
    padding-block: 0;
    background: var(--p-content-background);
    opacity: 0;
    transition: opacity 0.15s;
  }

  &:hover::before,
  &:focus-within::before,
  &:hover .insert-step,
  &:focus-within .insert-step {
    opacity: 1;
  }
}
</style>
