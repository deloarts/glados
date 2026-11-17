<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import ThumbnailCell from '@/core/components/ThumbnailCell.vue'
import { useProductDevicesViewStore } from '../stores/productDevicesViewStore'
import type { ProductDevice } from '../types/productDevice'

/**
 * The side panel of the overview: every device with its number, rendering,
 * name, kind and driving medium. The number is the device's place in the
 * list and matches the one on its marker. Hovering a row highlights its marker and brings
 * its card to the front; clicking it picks the device, which centres its
 * marker and, for an editor, lets the next click on the image place it. The
 * eye on each row hides or shows that device's marker, and the buttons above
 * the list do the same for every device at once. Beside them sits the switch
 * that hides the cards on the markers.
 */
const props = defineProps<{
  devices: ProductDevice[]
  imageUrl: (fileId: number | null) => string | null
  typeLabel: (device: ProductDevice) => string
  selectedId: number | null
  hoveredId: number | null
  hiddenIds: ReadonlySet<number>
}>()

const emit = defineEmits<{
  hover: [id: number | null]
  select: [id: number]
  'toggle-hidden': [id: number]
  'hide-all': []
  'show-all': []
}>()

const { t } = useI18n()
const { hideDetails } = storeToRefs(useProductDevicesViewStore())

const allHidden = computed(() => props.devices.every((d) => props.hiddenIds.has(d.id)))
</script>

<template>
  <Panel class="device-list-panel fill-panel">
    <template #header>
      <div class="panel-header-row">
        <span class="panel-title">{{ t('productDevices.devices.overview.listTitle') }}</span>
        <Tag :value="String(devices.length)" severity="secondary" />
      </div>
    </template>

    <p v-if="devices.length === 0" class="empty">{{ t('productDevices.devices.overview.listEmpty') }}</p>
    <div v-else class="list-actions">
      <Button
        type="button"
        icon="mdi mdi-card-off-outline"
        :label="t('productDevices.devices.overview.hideDetails')"
        severity="secondary"
        size="small"
        :text="!hideDetails"
        :aria-pressed="hideDetails"
        data-testid="product-devices-hide-details"
        @click="hideDetails = !hideDetails"
      />
      <span class="list-actions-spacer" />
      <Button
        type="button"
        icon="mdi mdi-eye-off-outline"
        :label="t('productDevices.devices.overview.hideAll')"
        severity="secondary"
        size="small"
        text
        :disabled="allHidden"
        data-testid="device-overview-hide-all"
        @click="emit('hide-all')"
      />
      <Button
        type="button"
        icon="mdi mdi-eye-outline"
        :label="t('productDevices.devices.overview.showAll')"
        severity="secondary"
        size="small"
        text
        :disabled="hiddenIds.size === 0"
        data-testid="device-overview-show-all"
        @click="emit('show-all')"
      />
    </div>
    <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- clears the row highlight, not an interaction -->
    <ul
      v-if="devices.length > 0"
      class="device-rows"
      @mouseleave="emit('hover', null)"
      @focusout="emit('hover', null)"
    >
      <li
        v-for="(device, index) in devices"
        :key="device.id"
        class="device-row"
        :class="{
          selected: device.id === selectedId,
          hovered: device.id === hoveredId,
          unplaced: device.marker_x === null,
          concealed: hiddenIds.has(device.id),
        }"
        role="button"
        tabindex="0"
        :aria-pressed="device.id === selectedId"
        data-testid="device-overview-list-row"
        @mouseenter="emit('hover', device.id)"
        @focus="emit('hover', device.id)"
        @click="emit('select', device.id)"
        @keydown.enter.prevent="emit('select', device.id)"
      >
        <span class="device-number" data-testid="device-overview-list-number">{{ index + 1 }}</span>
        <ThumbnailCell
          :src="imageUrl(device.rendering_file_id)"
          :item-name="device.name_utf8"
          size="2.5rem"
        />
        <span class="device-text">
          <span class="device-name">{{ device.name_utf8 }}</span>
          <span v-if="typeLabel(device)" class="device-type">{{ typeLabel(device) }}</span>
        </span>
        <i
          v-if="device.marker_x === null"
          v-tooltip.left="t('productDevices.devices.overview.notPlaced')"
          class="mdi mdi-map-marker-off-outline not-placed"
          :aria-label="t('productDevices.devices.overview.notPlaced')"
        />
        <Button
          type="button"
          :icon="hiddenIds.has(device.id) ? 'mdi mdi-eye-off-outline' : 'mdi mdi-eye-outline'"
          v-tooltip.left="
            hiddenIds.has(device.id)
              ? t('productDevices.devices.overview.showMarker')
              : t('productDevices.devices.overview.hideMarker')
          "
          :aria-label="
            hiddenIds.has(device.id)
              ? t('productDevices.devices.overview.showMarker')
              : t('productDevices.devices.overview.hideMarker')
          "
          :aria-pressed="hiddenIds.has(device.id)"
          severity="secondary"
          size="small"
          text
          rounded
          class="toggle-hidden"
          data-testid="device-overview-toggle-hidden"
          @click.stop="emit('toggle-hidden', device.id)"
          @keydown.enter.stop
        />
      </li>
    </ul>
  </Panel>
</template>

<style scoped lang="scss">
.device-list-panel {
  flex: 0 0 auto;
  min-height: 0;
  --p-panel-content-padding: var(--space-1);
}

.panel-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.empty {
  margin: var(--space-2);
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.device-rows {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.device-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--p-border-radius-sm);
  cursor: pointer;
  outline: none;

  &.hovered,
  &:focus-visible {
    background: var(--p-content-hover-background);
  }

  &.selected {
    background: var(--p-highlight-background);
    color: var(--p-highlight-color);
  }

  &.unplaced .device-name {
    color: var(--p-text-muted-color);
  }

  // A hidden device's marker is off the image, so its row fades back.
  &.concealed :deep(.thumb-cell),
  &.concealed .device-text {
    opacity: 0.5;
  }
}

.list-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-1);
  margin-bottom: var(--space-1);
}

// Pushes Hide all and Show all to the right, away from Hide detailed.
.list-actions-spacer {
  flex: 1;
}

.device-number {
  flex-shrink: 0;
  width: 1.5rem;
  height: 1.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--p-primary-color);
  color: var(--p-primary-contrast-color);
  font-size: var(--font-size-xs);
  font-weight: 600;
  line-height: 1;
}

.device-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.device-name {
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}

.device-type {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  overflow-wrap: anywhere;
}

.toggle-hidden {
  flex-shrink: 0;
}

.not-placed {
  color: var(--p-text-muted-color);
}
</style>
