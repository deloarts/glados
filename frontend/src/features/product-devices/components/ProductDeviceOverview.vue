<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { useAppToast } from '@/core/composables/useAppToast'
import { extractApiError } from '@/core/utils/errors'
import { useBlobObjectUrl } from '@/shared/composables/useBlobObjectUrl'
import { useLocalizedText } from '@/shared/composables/useLocalizedText'
import { useResizablePanelWidth } from '@/shared/composables/useResizablePanelWidth'
import {
  getDeviceImageBlob,
  getDeviceImageFiles,
  uploadDeviceOverview,
  type DeviceImageFile,
} from '../api/deviceImagesApi'
import { updateProductDevice } from '../api/productDevicesApi'
import { useDeviceRenderings } from '../composables/useDeviceRenderings'
import { useProductDeviceResourcesStore } from '../stores/productDeviceResourcesStore'
import { useProductDevicesViewStore } from '../stores/productDevicesViewStore'
import type { ProductDevice } from '../types/productDevice'
import { deviceFormFromDevice, deviceSaveRequest } from '../utils/deviceForm'
import DeviceOverviewCanvas, { type OverviewMarker } from './DeviceOverviewCanvas.vue'
import ProductDeviceOverviewList from './ProductDeviceOverviewList.vue'
import PanelResizeHandle from '@/shared/components/layout/PanelResizeHandle.vue'

/**
 * The product's top-down overview image with one marker per device, a
 * raster image or an SVG, which the backend cleans on upload. The image sits
 * in a zoomable canvas, with the list of devices in a panel beside it.
 * Picking a device jumps to its marker; an editor then places or moves the
 * marker by clicking the image. Markers can be hidden from the list to clear
 * a crowded image; a picked device always shows its marker. The position is stored
 * normalised to the image, so a re-rendered overview of the same framing
 * keeps every marker in place.
 */
const props = defineProps<{
  productId: number
  devices: ProductDevice[]
  canEdit: boolean
}>()

const emit = defineEmits<{ updated: [device: ProductDevice] }>()

const { t } = useI18n()
const toast = useAppToast()
const resources = useProductDeviceResourcesStore()
const { localize } = useLocalizedText()

const overview = ref<DeviceImageFile | null>(null)
const uploading = ref(false)
const selectedId = ref<number | null>(null)
const hoveredId = ref<number | null>(null)

/** The hovered device with the devices it moves with: its driver and the driver's other followers. */
const linkedToHovered = computed(() => {
  const hovered = props.devices.find((d) => d.id === hoveredId.value)
  if (!hovered) return new Set<number>()
  const driverId = hovered.driven_by_id ?? hovered.id
  return new Set(props.devices.filter((d) => d.id === driverId || d.driven_by_id === driverId).map((d) => d.id))
})
// Devices whose markers are off the image, for this visit only.
const hiddenIds = ref<ReadonlySet<number>>(new Set())
const { hideDetails } = storeToRefs(useProductDevicesViewStore())
const detailed = computed(() => !hideDetails.value)
const fileInput = ref<HTMLInputElement | null>(null)
const canvas = ref<InstanceType<typeof DeviceOverviewCanvas> | null>(null)

const { url } = useBlobObjectUrl(
  () => overview.value?.id ?? null,
  (fileId: number) => getDeviceImageBlob(props.productId, fileId),
  'image/png',
)

onMounted(async () => {
  void resources.load()
  const files = await getDeviceImageFiles(props.productId)
  overview.value = files.find((f) => f.category === 'device_overview') ?? null
})

const selected = computed(() => props.devices.find((d) => d.id === selectedId.value) ?? null)
const placing = computed(() => props.canEdit && selected.value !== null)
// Without the rights to edit the product, the overview's buttons stay
// visible but disabled with this tooltip.
const noRights = computed(() => (props.canEdit ? '' : t('productDevices.tags.noRights')))

// Each device is numbered by its place in the list, starting at 1, and its
// marker carries the same number.
const markers = computed<OverviewMarker[]>(() =>
  props.devices
    .map((d, index) => ({ d, number: index + 1 }))
    .filter(({ d }) => d.marker_x !== null && d.marker_y !== null)
    .filter(({ d }) => !hiddenIds.value.has(d.id) || d.id === selectedId.value)
    .map(({ d, number }) => ({
      id: d.id,
      number,
      x: d.marker_x as number,
      y: d.marker_y as number,
      label: d.name_utf8,
      highlighted: d.id === selectedId.value || linkedToHovered.value.has(d.id),
      typeLabel: typeLabel(d),
      imageUrl: urlFor(d.rendering_file_id),
    })),
)

/**
 * The device's type on its card, kind and driving medium, such as
 * "Linear drive | Pneumatics".
 */
function typeLabel(device: ProductDevice): string {
  const kind = resources.kindById.get(device.kind_id)
  const medium = device.driving_medium_id === null ? undefined : resources.optionById.get(device.driving_medium_id)
  return [kind && localize(kind.label), medium && localize(medium.label)]
    .filter(Boolean)
    .join(' | ')
}

function toggleHidden(id: number): void {
  const next = new Set(hiddenIds.value)
  if (!next.delete(id)) next.add(id)
  hiddenIds.value = next
}

// The cards and the device list both show the renderings.
const { urlFor } = useDeviceRenderings({
  productId: () => props.productId,
  fileIds: () => props.devices.map((d) => d.rendering_file_id),
})

// The device list on the right, its width dragged like the other side
// panels and kept per browser.
const {
  width: listWidth,
  isResizing,
  min: listMin,
  max: listMax,
  onResizeStart,
  onResizeKey,
} = useResizablePanelWidth({
  defaultWidth: 300,
  min: 220,
  max: () => window.innerWidth * 0.5,
  dockedTo: 'end',
  storageKey: 'glados.productDevices.overviewListWidth',
})

const deviceChoices = computed(() =>
  props.devices.map((d) => ({
    value: d.id,
    label: d.name_utf8,
    placed: d.marker_x !== null,
  })),
)

// Picking a placed device brings its marker into view.
watch(selectedId, () => {
  const device = selected.value
  if (device && device.marker_x !== null && device.marker_y !== null) {
    canvas.value?.centreOn(device.marker_x, device.marker_y)
  }
})

async function onOverviewChosen(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  uploading.value = true
  try {
    overview.value = await uploadDeviceOverview(props.productId, file)
  } catch (e) {
    toast.error(t('productDevices.devices.errors.uploadFailed'), extractApiError(e) ?? undefined)
  } finally {
    uploading.value = false
  }
}

async function saveMarker(device: ProductDevice, x: number | null, y: number | null): Promise<void> {
  await resources.load()
  const form = deviceFormFromDevice(device)
  form.marker_x = x
  form.marker_y = y
  const body = deviceSaveRequest(form, resources.kindById.get(device.kind_id))
  if (!body) return
  try {
    emit('updated', await updateProductDevice(device.id, device.edit_version, body))
  } catch (e) {
    toast.error(t('productDevices.devices.errors.unknown'), extractApiError(e) ?? undefined)
  }
}

async function onPlace(point: { x: number; y: number }): Promise<void> {
  const device = selected.value
  if (!device || !props.canEdit) return
  await saveMarker(device, point.x, point.y)
  selectedId.value = null
}

async function clearMarker(): Promise<void> {
  const device = selected.value
  if (device) await saveMarker(device, null, null)
  selectedId.value = null
}
</script>

<template>
  <div class="device-overview">
    <div class="overview-controls">
      <Select
        v-model="selectedId"
        :options="deviceChoices"
        option-label="label"
        option-value="value"
        filter
        show-clear
        :disabled="!url"
        :placeholder="
          canEdit
            ? t('productDevices.devices.overview.pickDevice')
            : t('productDevices.devices.overview.findDevice')
        "
        :aria-label="t('productDevices.devices.overview.pickDevice')"
        class="device-picker"
        data-testid="device-overview-picker"
      >
        <template #option="{ option }">
          <i
            :class="option.placed ? 'mdi mdi-map-marker' : 'mdi mdi-map-marker-off-outline'"
            class="option-icon"
            aria-hidden="true"
          />
          <span>{{ option.label }}</span>
        </template>
      </Select>
      <span v-tooltip.top="noRights || undefined">
        <Button
          type="button"
          icon="mdi mdi-map-marker-remove-outline"
          :label="t('productDevices.devices.overview.clearMarker')"
          severity="contrast"
          text
          :disabled="!canEdit || selected?.marker_x == null"
          data-testid="device-overview-clear-marker"
          @click="clearMarker"
        />
      </span>
      <span v-tooltip.top="noRights || undefined">
        <Button
          type="button"
          icon="mdi mdi-upload"
          :label="
            overview
              ? t('productDevices.devices.overview.replace')
              : t('productDevices.devices.overview.upload')
          "
          severity="contrast"
          text
          :disabled="!canEdit"
          :loading="uploading"
          data-testid="device-overview-upload"
          @click="fileInput?.click()"
        />
      </span>
      <template v-if="canEdit">
        <input
          ref="fileInput"
          type="file"
          aria-hidden="true"
          tabindex="-1"
          accept=".png,.jpg,.jpeg,.webp,.svg,image/png,image/jpeg,image/webp,image/svg+xml"
          class="file-input"
          data-testid="device-overview-input"
          @change="onOverviewChosen"
        />
      </template>
      <span v-if="placing" class="hint">
        {{ t('productDevices.devices.overview.clickToPlace') }}
      </span>
    </div>

    <div class="overview-body" :class="{ resizing: isResizing }">
      <DeviceOverviewCanvas
        v-if="url"
        ref="canvas"
        :src="url"
        :markers="markers"
        :placing="placing"
        :detailed="detailed"
        @place="onPlace"
        @marker-enter="hoveredId = $event"
        @marker-leave="hoveredId = null"
      />
      <div v-else class="overview-empty">
        <i class="mdi mdi-image-area" aria-hidden="true" />
        <span>{{ t('productDevices.devices.overview.empty') }}</span>
      </div>
      <PanelResizeHandle :width="listWidth" :min="listMin" :max="listMax" @start="onResizeStart" @key="onResizeKey" />
      <!-- eslint-disable-next-line vuejs-accessibility/mouse-events-have-key-events -- the list emits hover on keyboard focus as well -->
      <ProductDeviceOverviewList
        :style="{ width: `${listWidth}px` }"
        :devices="devices"
        :image-url="urlFor"
        :type-label="typeLabel"
        :selected-id="selectedId"
        :hovered-id="hoveredId"
        :hidden-ids="hiddenIds"
        @hover="hoveredId = $event"
        @select="selectedId = selectedId === $event ? null : $event"
        @toggle-hidden="toggleHidden"
        @hide-all="hiddenIds = new Set(devices.map((d) => d.id))"
        @show-all="hiddenIds = new Set()"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.device-overview {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.overview-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: row;
  gap: var(--space-1);

  &.resizing {
    user-select: none;
    cursor: ew-resize;
  }
}

.overview-controls {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.device-picker {
  min-width: 22rem;
}

.option-icon {
  margin-right: var(--space-2);
  color: var(--p-text-muted-color);
}

.overview-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  color: var(--p-text-muted-color);

  i {
    font-size: var(--font-size-4xl);
  }
}

.file-input {
  display: none;
}
</style>
