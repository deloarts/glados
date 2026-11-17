<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import type { DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'

import { useAppToast } from '@/core/composables/useAppToast'
import { useClipboard } from '@/core/composables/useClipboard'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { LiveResource } from '@/core/realtime/resources'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { extractApiError } from '@/core/utils/errors'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import ThumbnailCell from '@/core/components/ThumbnailCell.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import { useLocalizedText } from '@/shared/composables/useLocalizedText'
import { getDeviceCompleteness } from '../api/deviceCompletenessApi'
import { getProductDevices, setProductDeviceArchived } from '../api/productDevicesApi'
import { useDeviceRenderings } from '../composables/useDeviceRenderings'
import { useProductDeviceResourcesStore } from '../stores/productDeviceResourcesStore'
import { useProductDevicesViewStore } from '../stores/productDevicesViewStore'
import type {
  ProductDevice,
  ProductDeviceCompleteness,
  ProductDisciplines,
  SequenceCoverage,
} from '../types/productDevice'
import ProductDeviceDialog from './ProductDeviceDialog.vue'
import ProductDeviceCompletenessTable from './ProductDeviceCompletenessTable.vue'
import ProductDeviceOverview from './ProductDeviceOverview.vue'
import ProductPlcTagsTable from './ProductPlcTagsTable.vue'

/**
 * The Devices tab of a product: its devices with their names in UTF-8 and
 * ASCII, kind, driving medium, initial position and parts, or the overview
 * image with the device markers. The switches sit in the product page's
 * controls bar (ProductDevicesControls). The list follows changes made
 * elsewhere live: any change to a device of this product refetches it.
 */
const props = defineProps<{
  productId: number
  canEdit: boolean
  /** For the file name of the tag export. */
  productNumber?: string
  /** The machine's disciplines, for the plans a device rename names. */
  disciplines?: ProductDisciplines
  /**
   * Counts the calculations of the product per device, for the marks in the
   * list. The hosting page passes it from the calculation tools; without it
   * the list shows no marks.
   */
  countCalculations?: (productId: number) => Promise<Map<number, number>>
}>()

defineSlots<{
  /** The calculations section of the device dialog, passed on to it. */
  calculations?(props: {
    device: ProductDevice
    onLoaded: (calculations: Array<{ document_number: string; released_at: string | null }>) => void
  }): unknown
}>()

const hostStore = useHostStore()
const { t } = useI18n()
const toast = useAppToast()
const { localize } = useLocalizedText()
const resources = useProductDeviceResourcesStore()
const view = useProductDevicesViewStore()
const { mode, showArchived, showFullNames, createRequests } = storeToRefs(view)
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const devices = ref<ProductDevice[]>([])
const loading = ref(false)
watchLoadingBar(loading)

const { urlFor } = useDeviceRenderings({
  productId: () => props.productId,
  fileIds: () => devices.value.map((d) => d.rendering_file_id),
})

const dialogVisible = ref(false)
const editing = ref<ProductDevice | undefined>(undefined)
const completeness = ref<ProductDeviceCompleteness[]>([])

/** Whether a flow sequence moves or checks the device; a device in none is marked. */
function coverageOf(device: ProductDevice): SequenceCoverage {
  return completeness.value.find((c) => c.device_id === device.id)?.sequence_coverage ?? 'none'
}

let completenessSeq = 0
/** The plan ticks and sequence coverage, apart from the devices so the list never waits for them. */
async function loadCompleteness(): Promise<void> {
  const seq = ++completenessSeq
  try {
    const result = await getDeviceCompleteness(props.productId)
    if (seq === completenessSeq) completeness.value = result
  } catch {
    // The marks stay as they were until the next load.
  }
}

/** How many calculations refer to each device, by device id. */
const calculationCounts = ref<Map<number, number>>(new Map())

async function loadCalculationCounts(): Promise<void> {
  if (!props.countCalculations) return
  try {
    calculationCounts.value = await props.countCalculations(props.productId)
  } catch {
    // The marks stay as they were until the next load.
  }
}

let loadSeq = 0
/** `quiet` skips the loading bar, for refetches a live signal triggers. */
async function load(quiet = false): Promise<void> {
  const seq = ++loadSeq
  if (!quiet) loading.value = true
  void loadCompleteness()
  void loadCalculationCounts()
  try {
    const result = await getProductDevices(props.productId, showArchived.value)
    if (seq === loadSeq) devices.value = result
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

onMounted(() => {
  void resources.load()
  void load()
})
watch(showArchived, () => void load())
watch(createRequests, () => openCreate())

// ── Live ──────────────────────────────────────────────────────────────

// A device signal carries its product's id.
useLiveRefresh([LiveResource.PRODUCT_DEVICES], () => load(true), {
  debounceMs: 300,
  filter: (signal) => signal.action === 'bulk' || signal.id === props.productId,
})

function kindLabel(device: ProductDevice): string {
  const kind = resources.kindById.get(device.kind_id)
  return kind ? localize(kind.label) : ''
}

function mediumLabel(device: ProductDevice): string {
  if (device.driving_medium_id === null) return getEmptyPlaceholder()
  const medium = resources.optionById.get(device.driving_medium_id)
  return medium ? localize(medium.label) : (device.driving_medium_letter ?? '')
}

function initialPositionLabel(device: ProductDevice): string | null {
  if (device.initial_position_id === null) return null
  const own = device.position_labels[String(device.initial_position_id)]
  const position = resources.kindById
    .get(device.kind_id)
    ?.positions.find((p) => p.id === device.initial_position_id)
  const base = own ?? (position ? localize(position.label) : '')
  const value = device.initial_position_value
  return value === null ? base : `${base} ${value}${position?.unit ? ` ${position.unit}` : ''}`
}

/** The device this one moves with, by name; null when it is driven by none. */
function drivenByName(device: ProductDevice): string | null {
  if (device.driven_by_id === null) return null
  return devices.value.find((d) => d.id === device.driven_by_id)?.name_utf8 ?? `#${device.driven_by_id}`
}

/** The devices this one drives, by name, or null when it drives none. */
function drivenNames(device: ProductDevice): string | null {
  const names = devices.value.filter((d) => d.driven_by_id === device.id).map((d) => d.name_utf8)
  return names.length ? names.join(', ') : null
}

function roleLabel(roleId: number): string {
  const role = resources.optionById.get(roleId)
  return role ? localize(role.label) : ''
}

function openCreate(): void {
  editing.value = undefined
  dialogVisible.value = true
}

function openDevice(device: ProductDevice): void {
  editing.value = device
  dialogVisible.value = true
}

function replaceDevice(saved: ProductDevice): void {
  const index = devices.value.findIndex((d) => d.id === saved.id)
  if (index === -1) devices.value = [...devices.value, saved]
  else devices.value.splice(index, 1, saved)
}

function onSaved(saved: ProductDevice): void {
  replaceDevice(saved)
  toast.success(saved.name_utf8, t('productDevices.devices.saved'))
}

// ── Context menu ──────────────────────────────────────────────────────

const menu = ref<{ show: (event: Event) => void } | null>(null)
const menuDevice = ref<ProductDevice | null>(null)
const { copyToClipboard } = useClipboard()

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  menuDevice.value = event.data as ProductDevice
  menu.value?.show(event.originalEvent)
}

// The names follow the switch for the product number, so what is copied is
// what the table shows.
const menuItems = computed<MenuItem[]>(() => {
  const device = menuDevice.value
  if (!device) return []
  const utf8 = showFullNames.value ? device.full_name_utf8 : device.name_utf8
  const ascii = showFullNames.value ? device.full_name_ascii : device.name_ascii
  return [
    {
      label: props.canEdit
        ? t('productDevices.devices.editDevice')
        : t('productDevices.devices.showDevice'),
      icon: props.canEdit ? 'mdi mdi-pencil' : 'mdi mdi-eye-outline',
      command: () => openDevice(device),
    },
    { separator: true },
    {
      label: t('productDevices.devices.copyName'),
      icon: 'mdi mdi-content-copy',
      command: () => void copyToClipboard(utf8),
    },
    {
      label: t('productDevices.devices.copyAsciiName'),
      icon: 'mdi mdi-content-copy',
      command: () => void copyToClipboard(ascii),
    },
    { separator: true },
    {
      label: device.archived ? t('common.restore') : t('common.archive'),
      icon: device.archived ? 'mdi mdi-archive-arrow-up-outline' : 'mdi mdi-archive-outline',
      disabled: !props.canEdit,
      command: () => void toggleArchived(device),
    },
  ]
})


async function toggleArchived(device: ProductDevice): Promise<void> {
  try {
    const saved = await setProductDeviceArchived(device.id, !device.archived)
    if (saved.archived && !showArchived.value) {
      devices.value = devices.value.filter((d) => d.id !== saved.id)
    } else {
      replaceDevice(saved)
    }
  } catch (e) {
    toast.error(t('productDevices.devices.errors.unknown'), extractApiError(e) ?? undefined)
  }
}
</script>

<template>
  <div class="devices-tab">

    <ProductDeviceCompletenessTable
      v-if="mode === 'completeness'"
      :devices="devices"
      :completeness="completeness"
      :disciplines="disciplines"
      :can-edit="canEdit"
      @changed="load(true)"
    />

    <ProductPlcTagsTable
      v-else-if="mode === 'tags'"
      :product-id="productId"
      :product-number="productNumber ?? String(productId)"
      :can-edit="canEdit"
    />

    <ProductDeviceOverview
      v-else-if="mode === 'overview'"
      :product-id="productId"
      :devices="devices"
      :can-edit="canEdit"
      @updated="replaceDevice"
    />

    <DataTable
      v-else
      :value="devices"
      data-key="id"
      size="small"
      scrollable
      scroll-height="flex"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
      v-model:context-menu-selection="menuDevice"
      context-menu
      selection-mode="single"
      class="devices-table clickable-rows"
      @row-click="openDevice($event.data as ProductDevice)"
      @row-contextmenu="onRowContextMenu"
    >
      <template #empty>
        <EmptyState />
      </template>

      <Column header="#" class="column-fit" body-class="row-number">
        <template #body="{ index }">{{ index + 1 }}</template>
      </Column>
      <Column :header="t('productDevices.devices.columns.image')" class="column-fit">
        <template #body="{ data }: { data: ProductDevice }">
          <ThumbnailCell
            :src="urlFor(data.rendering_file_id)"
            :item-name="data.name_utf8"
            size="3rem"
          />
        </template>
      </Column>
      <Column v-if="showFullNames" :header="t('productDevices.devices.columns.fullNameUtf8')" class="column-fit">
        <template #body="{ data }: { data: ProductDevice }">{{ data.full_name_utf8 }}</template>
      </Column>
      <Column :header="t('productDevices.devices.columns.nameUtf8')" class="column-fit">
        <template #body="{ data }: { data: ProductDevice }">
          {{ data.name_utf8 }}
          <i
            v-if="hostStore.sequencesEnabled && !data.archived && coverageOf(data) === 'none'"
            v-tooltip.bottom="t('productDevices.completeness.notInSequence')"
            class="mdi mdi-sitemap-outline not-in-sequence"
            :aria-label="t('productDevices.completeness.notInSequence')"
            :data-testid="`device-not-in-sequence-${data.id}`"
          />
          <i
            v-if="calculationCounts.get(data.id)"
            v-tooltip.bottom="t('productDevices.calculations.count', { n: calculationCounts.get(data.id) }, calculationCounts.get(data.id) ?? 0)"
            class="mdi mdi-calculator-variant-outline has-calculations"
            :aria-label="t('productDevices.calculations.count', { n: calculationCounts.get(data.id) }, calculationCounts.get(data.id) ?? 0)"
            :data-testid="`device-calculations-${data.id}`"
          />
          <Tag v-if="data.archived" :value="t('common.archivedTag')" severity="warn" class="ml-tag" />
          <Tag
            v-if="drivenByName(data)"
            :value="t('productDevices.devices.drivenByTag', { name: drivenByName(data) })"
            severity="secondary"
            icon="mdi mdi-link-variant"
            class="ml-tag"
            data-testid="device-driven-by"
          />
          <Tag
            v-if="drivenNames(data)"
            :value="t('productDevices.devices.drivesTag', { names: drivenNames(data) })"
            severity="secondary"
            icon="mdi mdi-link-variant"
            class="ml-tag"
          />
        </template>
      </Column>
      <Column v-if="showFullNames" :header="t('productDevices.devices.columns.fullNameAscii')" class="column-fit">
        <template #body="{ data }: { data: ProductDevice }">
          <code>{{ data.full_name_ascii }}</code>
        </template>
      </Column>
      <Column :header="t('productDevices.devices.columns.nameAscii')" class="column-fit">
        <template #body="{ data }: { data: ProductDevice }">
          <code>{{ data.name_ascii }}</code>
        </template>
      </Column>
      <Column :header="t('productDevices.devices.columns.kind')" class="column-fit">
        <template #body="{ data }: { data: ProductDevice }">{{ kindLabel(data) }}</template>
      </Column>
      <Column :header="t('productDevices.devices.columns.drivingMedium')" class="column-fit">
        <template #body="{ data }: { data: ProductDevice }">{{ mediumLabel(data) }}</template>
      </Column>
      <Column :header="t('productDevices.devices.columns.initialPosition')" class="column-fit">
        <template #body="{ data }: { data: ProductDevice }">
          <span v-if="initialPositionLabel(data)">{{ initialPositionLabel(data) }}</span>
          <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
        </template>
      </Column>
      <Column :header="t('productDevices.devices.columns.components')">
        <template #body="{ data }: { data: ProductDevice }">
          <div class="component-tags">
            <Tag
              v-for="component in data.components"
              :key="component.id"
              :value="component.eplan_tag ? `${roleLabel(component.role_id)} ${component.eplan_tag}` : roleLabel(component.role_id)"
              severity="secondary"
            />
            <span v-if="data.components.length === 0" class="text-muted">{{ getEmptyPlaceholder() }}</span>
          </div>
        </template>
      </Column>
      <Column :header="t('productDevices.devices.columns.flags')" class="column-fit">
        <template #body="{ data }: { data: ProductDevice }">
          <Tag
            v-if="data.safety_relevant"
            :value="t('productDevices.devices.safetyTag')"
            severity="danger"
            icon="mdi mdi-shield-alert-outline"
          />
        </template>
      </Column>
    </DataTable>

    <ContextMenu ref="menu" :model="menuItems" @hide="menuDevice = null" />

    <ProductDeviceDialog
      v-model:visible="dialogVisible"
      :product-id="productId"
      :device="editing"
      :devices="devices"
      :disciplines="disciplines"
      :sequence-coverage="editing && hostStore.sequencesEnabled ? coverageOf(editing) : undefined"
      :readonly="!canEdit"
      @saved="onSaved"
    >
      <template v-if="$slots.calculations" #calculations="slotProps">
        <slot name="calculations" v-bind="slotProps" />
      </template>
    </ProductDeviceDialog>
  </div>
</template>

<style scoped lang="scss">
.devices-tab {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.devices-table {
  flex: 1;
  min-height: 0;
}

.component-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.not-in-sequence {
  margin-left: var(--space-1);
  color: var(--p-orange-500);
}

.has-calculations {
  margin-left: var(--space-1);
  color: var(--p-text-muted-color);
}

.ml-tag {
  margin-left: var(--space-2);
}

.text-muted {
  color: var(--p-text-muted-color);
}
</style>
