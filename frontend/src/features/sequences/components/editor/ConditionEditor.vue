<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { MenuItem } from 'openvue/menuitem'

import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import type { SequenceConditionKind, SequenceConditionTerm } from '../../types/sequence'
import { useSequenceEditor } from '../../composables/sequenceEditorContext'
import { newTerm } from '../../utils/factories'
import DevicePositionPicker from './DevicePositionPicker.vue'
import VariantValueInput from './VariantValueInput.vue'

/**
 * A condition: terms that must all hold (AND). A term is a device in a
 * position, a device value compared with a threshold, another step
 * complete, time since the step became active (t/Xn) or anything outside
 * the device list described in words, such as "robot ready". Read-only,
 * each term reads as text. Suggested terms, such as the positions the step moves its
 * devices to, are offered to add with one click.
 */
const props = defineProps<{
  /** The step the condition belongs to; it is left out of the step terms. */
  stepKey: string
  addLabel: string
  /** Terms offered to add with one click; the caller leaves out those already held. */
  suggestions?: SequenceConditionTerm[]
}>()

const terms = defineModel<SequenceConditionTerm[]>({ required: true })

const { t } = useI18n()
const { names, readonly, stepOptions } = useSequenceEditor()

const KINDS: Array<{ kind: SequenceConditionKind; icon: string }> = [
  { kind: 'device_position', icon: 'mdi mdi-crosshairs-gps' },
  { kind: 'device_value', icon: 'mdi mdi-gauge' },
  { kind: 'step_complete', icon: 'mdi mdi-check-circle-outline' },
  { kind: 'time', icon: 'mdi mdi-timer-outline' },
  { kind: 'external', icon: 'mdi mdi-antenna' },
]

const menu = ref<{ toggle: (event: Event) => void } | null>(null)
const menuItems = computed<MenuItem[]>(() =>
  KINDS.map(({ kind, icon }) => ({
    label: t(`sequences.conditions.${kind}`),
    icon,
    command: () => (terms.value = [...terms.value, newTerm(kind)]),
  })),
)

const otherSteps = computed(() => stepOptions.value.filter((option) => option.key !== props.stepKey))

const comparators = computed(() => [
  { value: 'ge', label: '≥' },
  { value: 'le', label: '≤' },
])

function update(index: number, patch: Partial<SequenceConditionTerm>): void {
  terms.value = terms.value.map((term, i) => (i === index ? { ...term, ...patch } : term))
}

function remove(index: number): void {
  terms.value = terms.value.filter((_, i) => i !== index)
}

function stepLabel(key: string | null | undefined): string {
  return otherSteps.value.find((option) => option.key === key)?.label ?? getEmptyPlaceholder()
}

const offered = computed(() =>
  (props.suggestions ?? []).map((term) => {
    const position = names.position(term.device_id, term.position_id)
    return {
      term,
      label: `${names.deviceName(term.device_id)}: ${names.positionName(term.device_id, term.position_id)}`,
      // Only a position no sensor confirms is flagged; one not known is not.
      unconfirmed: position?.confirmed === false,
    }
  }),
)

function addTerms(added: SequenceConditionTerm[]): void {
  terms.value = [...terms.value, ...added]
}

function unitOf(term: SequenceConditionTerm): string | null {
  return names.position(term.device_id, term.position_id)?.unit ?? null
}
</script>

<template>
  <div class="condition" :class="{ readonly }">
    <div v-for="(term, index) in terms" :key="index" class="term" data-testid="sequence-term">
      <span v-if="index > 0" class="and">{{ t('sequences.conditions.and') }}</span>
      <span class="term-kind">{{ t(`sequences.conditions.${term.kind}`) }}</span>
      <div v-if="readonly" class="term-fields term-text">
        <template v-if="term.kind === 'device_position' || term.kind === 'device_value'">
          <DevicePositionPicker
            :position-optional="term.kind === 'device_value'"
            :device-id="term.device_id ?? null"
            :position-id="term.position_id ?? null"
          />
          <template v-if="term.kind === 'device_value'">
            <span>{{ term.comparator === 'le' ? '≤' : '≥' }}</span>
            <VariantValueInput :model-value="term.value ?? null" :unit="unitOf(term)" />
          </template>
        </template>
        <span v-else-if="term.kind === 'step_complete'">{{ stepLabel(term.step_key) }}</span>
        <VariantValueInput v-else-if="term.kind === 'time'" :model-value="term.duration_ms ?? null" unit="ms" />
        <span v-else>{{ term.text || getEmptyPlaceholder() }}</span>
      </div>
      <div v-else class="term-fields">
        <template v-if="term.kind === 'device_position'">
          <DevicePositionPicker
            :device-id="term.device_id ?? null"
            :position-id="term.position_id ?? null"
            @update:device-id="(id) => update(index, { device_id: id, position_id: null })"
            @update:position-id="(id) => update(index, { position_id: id })"
          />
        </template>
        <template v-else-if="term.kind === 'device_value'">
          <DevicePositionPicker
            position-optional
            :device-id="term.device_id ?? null"
            :position-id="term.position_id ?? null"
            @update:device-id="(id) => update(index, { device_id: id, position_id: null })"
            @update:position-id="(id) => update(index, { position_id: id })"
          />
          <div class="compare">
            <SelectButton
              :model-value="term.comparator ?? 'ge'"
              :options="comparators"
              option-label="label"
              option-value="value"
              :allow-empty="false"
              size="small"
              @update:model-value="(value: 'ge' | 'le') => update(index, { comparator: value })"
            />
            <VariantValueInput
              :model-value="term.value ?? null"
              :unit="unitOf(term)"
              @update:model-value="(value) => update(index, { value })"
            />
          </div>
        </template>
        <template v-else-if="term.kind === 'step_complete'">
          <Select
            :aria-label="t('sequences.editor.step')"
            :model-value="term.step_key ?? null"
            :options="otherSteps"
            option-label="label"
            option-value="key"
            :placeholder="t('sequences.editor.step')"
            size="small"
            @update:model-value="(key: string | null) => update(index, { step_key: key })"
          />
        </template>
        <template v-else-if="term.kind === 'time'">
          <VariantValueInput
            :model-value="term.duration_ms ?? null"
            unit="ms"
            :min="0"
            @update:model-value="(value) => update(index, { duration_ms: value })"
          />
        </template>
        <template v-else>
          <InputText
            :model-value="term.text ?? ''"
            :placeholder="t('sequences.editor.signal')"
            maxlength="500"
            size="small"
            fluid
            @update:model-value="(text) => update(index, { text: text || null })"
          />
        </template>
      </div>
      <Button
        v-if="!readonly"
        v-tooltip.bottom="t('sequences.editor.removeTerm')"
        :aria-label="t('sequences.editor.removeTerm')"
        icon="mdi mdi-close"
        severity="secondary"
        text
        size="small"
        @click="remove(index)"
      />
    </div>
    <div v-if="!readonly && offered.length > 0" class="suggestions" data-testid="sequence-suggestions">
      <span class="suggested">{{ t('sequences.editor.suggested') }}</span>
      <Button
        v-for="option in offered"
        :key="`${option.term.device_id}:${option.term.position_id}`"
        v-tooltip.bottom="option.unconfirmed ? t('sequences.editor.unconfirmedPosition') : undefined"
        :label="option.label"
        :icon="option.unconfirmed ? 'mdi mdi-alert-outline' : 'mdi mdi-plus'"
        :severity="option.unconfirmed ? 'warn' : 'secondary'"
        outlined
        size="small"
        data-testid="sequence-suggestion"
        @click="addTerms([option.term])"
      />
      <Button
        v-if="offered.length > 1"
        :label="t('sequences.editor.addAllSuggested')"
        icon="mdi mdi-playlist-plus"
        severity="secondary"
        text
        size="small"
        data-testid="sequence-suggestion-all"
        @click="addTerms(offered.map((option) => option.term))"
      />
    </div>
    <template v-if="!readonly">
      <Button
        :label="addLabel"
        icon="mdi mdi-plus"
        severity="secondary"
        text
        size="small"
        class="add"
        data-testid="sequence-add-term"
        @click="menu?.toggle($event)"
      />
      <Menu ref="menu" :model="menuItems" popup />
    </template>
  </div>
</template>

<style scoped lang="scss">
.condition {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.term {
  display: grid;
  grid-template-columns: 2.5rem 9rem 1fr auto;
  gap: var(--space-2);
  align-items: start;
}

.and {
  grid-column: 1;
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--p-text-muted-color);
  padding-top: var(--space-2);
}

.term-kind {
  grid-column: 2;
  font-size: var(--font-size-sm);
  padding-top: var(--space-2);
}

.term-fields {
  grid-column: 3;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

// Read-only, a term's parts sit on one line with the kind before them.
.term-text {
  flex-direction: row;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
}

// Without inputs to line up with, the labels sit on the text line.
.condition.readonly {
  .and,
  .term-kind {
    padding-top: 0;
  }

  .term-kind {
    color: var(--p-text-muted-color);
  }
}

.compare {
  display: flex;
  gap: var(--space-2);
  align-items: flex-start;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  align-items: center;
}

.suggested {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.add {
  align-self: flex-start;
}
</style>
