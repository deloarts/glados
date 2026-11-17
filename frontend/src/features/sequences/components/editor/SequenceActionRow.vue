<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import type { SequenceAction, SequenceActionQualifier } from '../../types/sequence'
import { useSequenceEditor } from '../../composables/sequenceEditorContext'
import ConditionEditor from './ConditionEditor.vue'
import DevicePositionPicker from './DevicePositionPicker.vue'
import VariantValueInput from './VariantValueInput.vue'

/**
 * One action of a step: a device moved to a position, with a value where
 * the position takes one, or something described in words. Its qualifier
 * says how long it applies (stored, continuous or pulse, after GRAFCET),
 * and an optional condition must hold before it starts. Its estimated
 * time is the device's travel time to the position unless it brings its own.
 * Read-only, the action reads as a line of text with its qualifier as a tag,
 * and its time, note and condition show only where it has them.
 */
const props = defineProps<{ stepKey: string }>()

const action = defineModel<SequenceAction>({ required: true })
const emit = defineEmits<{ remove: [] }>()

const { t } = useI18n()
const { names, readonly } = useSequenceEditor()

const QUALIFIERS: SequenceActionQualifier[] = ['stored', 'continuous', 'pulse']
const qualifierOptions = computed(() =>
  QUALIFIERS.map((value) => ({ value, label: t(`sequences.qualifiers.${value}.short`), tooltip: t(`sequences.qualifiers.${value}.long`) })),
)

const qualifier = computed(
  () => qualifierOptions.value.find((option) => option.value === (action.value.qualifier ?? 'stored')) ?? qualifierOptions.value[0]!,
)

const position = computed(() => names.position(action.value.device_id, action.value.position_id))
const showCondition = ref((action.value.condition ?? []).length > 0)
const showTime = ref(action.value.duration_ms != null)

const travelTime = computed(() => (action.value.kind === 'device' ? (position.value?.travelTimeMs ?? null) : null))
const timePlaceholder = computed(() =>
  travelTime.value === null ? t('sequences.timing.noTime') : t('sequences.timing.travelTime', { ms: travelTime.value }),
)

function patch(next: Partial<SequenceAction>): void {
  action.value = { ...action.value, ...next }
}

function setKind(kind: SequenceAction['kind']): void {
  if (kind === action.value.kind) return
  patch({ kind, device_id: null, position_id: null, value: null, text: null })
}

function setPosition(positionId: number | null): void {
  const next = names.position(action.value.device_id, positionId)
  patch({ position_id: positionId, value: next?.takesValue ? (action.value.value ?? null) : null })
}
</script>

<template>
  <div v-if="readonly" class="action readonly" data-testid="sequence-action">
    <div class="action-main">
      <i
        v-tooltip.bottom="t(`sequences.editor.kinds.${action.kind}`)"
        :class="action.kind === 'device' ? 'mdi mdi-cog-outline' : 'mdi mdi-text'"
        :aria-label="t(`sequences.editor.kinds.${action.kind}`)"
        class="kind-icon"
      />
      <div class="target">
        <template v-if="action.kind === 'device'">
          <DevicePositionPicker :device-id="action.device_id ?? null" :position-id="action.position_id ?? null" />
          <VariantValueInput v-if="position?.takesValue" :model-value="action.value ?? null" :unit="position.unit" />
        </template>
        <span v-else data-testid="sequence-action-text">{{ action.text || getEmptyPlaceholder() }}</span>
      </div>
      <span v-if="action.duration_ms" v-tooltip.bottom="t('sequences.timing.actionTime')" class="time">
        <i class="mdi mdi-timer-outline" aria-hidden="true" />
        <VariantValueInput :model-value="action.duration_ms" unit="ms" />
      </span>
      <Tag
        v-tooltip.bottom="qualifier.tooltip"
        :value="qualifier.label"
        severity="secondary"
        class="qualifier-tag"
        data-testid="sequence-action-qualifier"
      />
    </div>
    <p v-if="action.description" class="note">{{ action.description }}</p>
    <div v-if="(action.condition ?? []).length > 0" class="action-condition">
      <span class="label">{{ t('sequences.editor.actionConditionHint') }}</span>
      <ConditionEditor
        :model-value="action.condition ?? []"
        :step-key="props.stepKey"
        :add-label="t('sequences.editor.addTerm')"
      />
    </div>
  </div>
  <div v-else class="action" data-testid="sequence-action">
    <div class="action-main">
      <SelectButton
        :model-value="action.kind"
        :options="[
          { value: 'device', icon: 'mdi mdi-cog-outline', label: t('sequences.editor.kinds.device') },
          { value: 'text', icon: 'mdi mdi-text', label: t('sequences.editor.kinds.text') },
        ]"
        option-label="label"
        option-value="value"
        data-key="value"
        :allow-empty="false"
        size="small"
        class="kind"
        @update:model-value="setKind"
      >
        <template #option="{ option }">
          <i v-tooltip.bottom="option.label" :class="option.icon" :aria-label="option.label" />
        </template>
      </SelectButton>
      <div class="target">
        <template v-if="action.kind === 'device'">
          <DevicePositionPicker
            for-action
            :device-id="action.device_id ?? null"
            :position-id="action.position_id ?? null"
            @update:device-id="(id) => patch({ device_id: id, position_id: null, value: null })"
            @update:position-id="setPosition"
          />
          <VariantValueInput
            v-if="position?.takesValue"
            :model-value="action.value ?? null"
            :unit="position.unit"
            @update:model-value="(value) => patch({ value })"
          />
        </template>
        <InputText
          v-else
          :model-value="action.text ?? ''"
          :placeholder="t('sequences.editor.actionText')"
          maxlength="500"
          size="small"
          fluid
          data-testid="sequence-action-text"
          @update:model-value="(text) => patch({ text: text || null })"
        />
      </div>
      <SelectButton
        :model-value="action.qualifier ?? 'stored'"
        :options="qualifierOptions"
        option-label="label"
        option-value="value"
        :allow-empty="false"
        size="small"
        class="qualifier"
        @update:model-value="(qualifier: SequenceActionQualifier) => patch({ qualifier })"
      >
        <template #option="{ option }">
          <span v-tooltip.bottom="option.tooltip">{{ option.label }}</span>
        </template>
      </SelectButton>
      <div class="row-buttons">
        <Button
          v-tooltip.bottom="t('sequences.editor.actionCondition')"
          :aria-label="t('sequences.editor.actionCondition')"
          icon="mdi mdi-lock-outline"
          severity="secondary"
          :text="!showCondition"
          size="small"
          @click="showCondition = !showCondition"
        />
        <Button
          v-tooltip.bottom="t('sequences.timing.actionTime')"
          :aria-label="t('sequences.timing.actionTime')"
          icon="mdi mdi-timer-outline"
          severity="secondary"
          :text="!showTime"
          size="small"
          data-testid="sequence-action-time-toggle"
          @click="showTime = !showTime"
        />
        <Button
          v-tooltip.bottom="t('sequences.editor.removeAction')"
          :aria-label="t('sequences.editor.removeAction')"
          icon="mdi mdi-delete-outline"
          severity="secondary"
          text
          size="small"
          data-testid="sequence-remove-action"
          @click="emit('remove')"
        />
      </div>
    </div>
    <InputText
      :model-value="action.description ?? ''"
      :placeholder="t('sequences.editor.actionDescription')"
      maxlength="500"
      size="small"
      fluid
      class="description"
      @update:model-value="(description) => patch({ description: description || null })"
    />
    <div v-if="showTime" class="action-condition action-time">
      <span class="label">{{ t('sequences.timing.actionTimeHint') }}</span>
      <VariantValueInput
        :model-value="action.duration_ms ?? null"
        :min="0"
        unit="ms"
        :placeholder="timePlaceholder"
        data-testid="sequence-action-time"
        @update:model-value="(duration_ms) => patch({ duration_ms })"
      />
    </div>
    <div v-if="showCondition" class="action-condition">
      <span class="label">{{ t('sequences.editor.actionConditionHint') }}</span>
      <ConditionEditor
        :model-value="action.condition ?? []"
        :step-key="props.stepKey"
        :add-label="t('sequences.editor.addTerm')"
        @update:model-value="(condition) => patch({ condition })"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.action {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.action-main {
  display: flex;
  gap: var(--space-2);
  align-items: flex-start;
  flex-wrap: wrap;
}

.target {
  flex: 1 1 20rem;
  display: flex;
  gap: var(--space-2);
  align-items: flex-start;
  flex-wrap: wrap;
  min-width: 0;

  > :first-child {
    flex: 1 1 16rem;
  }
}

.action.readonly {
  gap: var(--space-1);
  padding: var(--space-2) var(--space-2);

  .action-main {
    align-items: baseline;
  }

  .target {
    align-items: baseline;

    > :first-child {
      flex: 0 1 auto;
    }
  }
}

.kind-icon {
  color: var(--p-text-muted-color);
}

.time {
  display: inline-flex;
  gap: var(--space-1);
  align-items: baseline;
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.qualifier-tag {
  min-width: 1.75rem;
}

.note {
  margin: 0;
  padding-left: var(--space-5);
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.row-buttons {
  display: flex;
}

.description {
  font-size: var(--font-size-sm);
}

.action-condition {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding-left: var(--space-2);
  border-left: 2px solid var(--p-content-border-color);

  .label {
    font-size: var(--font-size-sm);
    color: var(--p-text-muted-color);
  }
}

.action-time :deep(.variant-value) {
  max-width: 20rem;
}
</style>
