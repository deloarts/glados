<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import ThumbnailCell from '@/core/components/ThumbnailCell.vue'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { useDeviceRenderings } from '@/features/product-devices'
import EmptyState from '@/shared/components/EmptyState.vue'
import type { SequenceDocument } from '../composables/useSequenceDocument'
import type { SequenceNames } from '../composables/useSequenceNames'
import { stateName } from '../utils/positionNames'

/**
 * The start state of a sequence: each device of the product in its initial
 * position, as the devices define it. A released revision shows the state
 * frozen at its release. Changed on the devices, never here. The image is
 * the device's current rendering, also for a released revision. Clicking
 * a row opens the device.
 */
const props = defineProps<{ doc: SequenceDocument; names: SequenceNames }>()

const emit = defineEmits<{ open: [deviceId: number] }>()

const { t } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const renderingOf = computed(() => new Map(props.doc.devices.value.map((device) => [device.id, device.rendering_file_id])))
const { urlFor } = useDeviceRenderings({
  productId: () => props.doc.sequence.value?.product_id ?? 0,
  fileIds: () => [...renderingOf.value.values()],
  enabled: () => props.doc.sequence.value !== null,
})

const rows = computed(() =>
  props.names.devices.value
    .filter((device) => !device.archived)
    .map((device) => {
      const position = device.positions.find((p) => p.id === device.initialPositionId)
      const value = device.initialPositionValue
      const unit = position?.unit ? ` ${position.unit}` : ''
      return {
        id: device.id,
        rendering: renderingOf.value.get(device.id) ?? null,
        name: device.name,
        kind: device.kind,
        position: position ? `${stateName(position)}${value === null ? '' : ` ${value}${unit}`}` : null,
      }
    }),
)
</script>

<template>
  <div class="card start-state" data-testid="sequence-start-state">
    <p class="hint">{{ t('sequences.editor.startStateHint') }}</p>
    <DataTable
      :value="rows"
      data-key="id"
      size="small"
      scrollable
      scroll-height="flex"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
      selection-mode="single"
      class="table"
      @row-click="emit('open', $event.data.id)"
    >
      <template #empty>
        <EmptyState :message="t('sequences.editor.noDevices')" icon="mdi mdi-cog-outline" />
      </template>
      <Column header="#" class="column-fit" body-class="row-number">
        <template #body="{ index }">{{ index + 1 }}</template>
      </Column>
      <Column :header="t('sequences.editor.image')" class="column-fit">
        <template #body="{ data }">
          <ThumbnailCell :src="urlFor(data.rendering)" :item-name="data.name" size="3rem" />
        </template>
      </Column>
      <Column :header="t('sequences.editor.device')" class="column-fit">
        <template #body="{ data }">{{ data.name }}</template>
      </Column>
      <Column :header="t('sequences.editor.kind')" class="column-fit">
        <template #body="{ data }">{{ data.kind }}</template>
      </Column>
      <Column :header="t('sequences.editor.initialPosition')">
        <template #body="{ data }">
          <span v-if="data.position">{{ data.position }}</span>
          <span v-else class="muted">{{ getEmptyPlaceholder() }}</span>
        </template>
      </Column>
    </DataTable>
  </div>
</template>

<style scoped lang="scss">
.start-state {
  gap: var(--space-2);
}

.hint {
  flex-shrink: 0;
  margin: var(--space-1) var(--space-2) 0;
}

.table {
  flex: 1 1 auto;
  min-height: 0;
}

.muted {
  color: var(--p-text-muted-color);
}
</style>
