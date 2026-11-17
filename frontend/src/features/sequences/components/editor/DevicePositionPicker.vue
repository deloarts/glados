<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { useSequenceEditor } from '../../composables/sequenceEditorContext'
import type { SequencePositionName } from '../../composables/useSequenceNames'
import { stateName } from '../../utils/positionNames'

/**
 * A device of the product and one of its positions; for an action, a
 * position reads as the command that drives to it. Archived devices and
 * positions are offered only while already chosen, so an older step keeps
 * reading right without inviting new references. Read-only, the two read
 * as text.
 */
const props = defineProps<{
  positionOptional?: boolean
  /** An action target: a driven device moves with its driver, so it is offered disabled. */
  forAction?: boolean
}>()

const deviceId = defineModel<number | null>('deviceId', { default: null })
const positionId = defineModel<number | null>('positionId', { default: null })

const { t } = useI18n()
const { names, readonly } = useSequenceEditor()

const deviceOptions = computed(() =>
  names.devices.value
    .filter((device) => !device.archived || device.id === deviceId.value)
    .map((device) => {
      const moves = props.forAction && device.drivenById !== null
      return {
        value: device.id,
        label: device.name,
        kind: moves
          ? t('sequences.editor.movesWith', { name: names.deviceName(device.drivenById) })
          : device.kind,
        disabled: moves && device.id !== deviceId.value,
      }
    }),
)

const positionOptions = computed(() => {
  const device = deviceId.value == null ? undefined : names.deviceById.value.get(deviceId.value)
  return (device?.positions ?? [])
    .filter((position) => !position.archived || position.id === positionId.value)
    .map((position) => ({ value: position.id, label: optionLabel(position) }))
})

/**
 * The kind's name for the position, or for an action its command, then the
 * device's own label and the unit in brackets.
 */
function optionLabel(position: SequencePositionName): string {
  const name = props.forAction ? names.actionName(deviceId.value, position.id) : stateName(position)
  return position.unit ? `${name} (${position.unit})` : name
}

function setDevice(id: number | null): void {
  if (id === deviceId.value) return
  deviceId.value = id
  // A position belongs to the device's kind, so a new device starts without one.
  positionId.value = null
}
</script>

<template>
  <div v-if="readonly" class="device-position-text" data-testid="sequence-device-text">
    <span class="device-name">{{ deviceId == null ? getEmptyPlaceholder() : names.deviceName(deviceId) }}</span>
    <span v-if="positionId != null" class="position-name">{{
      props.forAction ? names.actionName(deviceId, positionId) : names.positionName(deviceId, positionId)
    }}</span>
    <span v-else-if="props.positionOptional" class="position-name">{{ t('sequences.editor.anyPosition') }}</span>
  </div>
  <div v-else class="device-position">
    <Select
      :aria-label="t('sequences.editor.device')"
      :model-value="deviceId"
      :options="deviceOptions"
      option-label="label"
      option-value="value"
      option-disabled="disabled"
      :placeholder="t('sequences.editor.device')"
      filter
      size="small"
      class="device"
      data-testid="sequence-device"
      @update:model-value="setDevice"
    >
      <template #option="{ option }">
        <span class="option-name">{{ option.label }}</span>
        <span class="option-kind">{{ option.kind }}</span>
      </template>
    </Select>
    <Select
      v-model="positionId"
      :aria-label="t('sequences.editor.position')"
      :options="positionOptions"
      option-label="label"
      option-value="value"
      :placeholder="props.positionOptional ? t('sequences.editor.anyPosition') : t('sequences.editor.position')"
      :show-clear="props.positionOptional"
      :disabled="deviceId == null"
      size="small"
      class="position"
      data-testid="sequence-position"
    />
  </div>
</template>

<style scoped lang="scss">
// Read-only, the device and its position read as one phrase.
.device-position-text {
  display: flex;
  gap: var(--space-1);
  align-items: baseline;
  flex-wrap: wrap;
  min-width: 0;
}

.device-name {
  font-weight: 600;
}

.device-position {
  display: flex;
  gap: var(--space-1);
  flex-wrap: wrap;
}

.device {
  flex: 2 1 12rem;
  min-width: 0;
}

.position {
  flex: 1 1 8rem;
  min-width: 0;
}

.option-name {
  margin-right: var(--space-2);
}

.option-kind {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}
</style>
