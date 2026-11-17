<script setup lang="ts">
import { computed, onBeforeUnmount, ref, toRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import type { DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'

import { scrapReasonLabelKey } from '@/shared/utils/scrapReasons'
import type { ScrapReason } from '@/shared/utils/scrapReasons'
import { storeToRefs } from 'pinia'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { useClipboard } from '@/core/composables/useClipboard'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import EmptyState from '@/shared/components/EmptyState.vue'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import { useAppToast } from '@/core/composables/useAppToast'
import { orderItemActionGates } from '../composables/useOrderItemActions'
import { useDeliveryPictures } from '../composables/useDeliveryPictures'
import { getOrderFileBlob } from '../api/getOrderFileBlob'
import CorrectDeliveryDialog from './CorrectDeliveryDialog.vue'
import type { CorrectionMode } from './CorrectDeliveryDialog.vue'

import type { DeliveryRecord, OrderFile, OrderItemResponse } from '../types/ordersResponse'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { formatUnit } from '@/shared/utils/units'

const props = defineProps<{
  visible: boolean
  item: OrderItemResponse | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const { t } = useI18n()
const { hasPermission } = usePermissions()

// A delivery row is corrected through its own dialog; afterwards the order is
// read again, so this dialog closes rather than show the line it was opened
// with.
const correctionTarget = ref<DeliveryRecord | null>(null)
const correctionMode = ref<CorrectionMode>('miscount')
const showCorrectDialog = ref(false)

// The line's state decides whether a row offers a correction; without
// receive:deliveries the button stays visible but disabled.
function correctionOffered(record: DeliveryRecord): boolean {
  if (!props.item) return false
  return orderItemActionGates.correctDelivery(props.item, record, {
    canWrite: false,
    canManage: false,
    canReceiveDeliveries: true,
  })
}
const canReceiveDeliveries = computed(() => hasPermission(Permission.RECEIVE_DELIVERIES))
const { missing } = useMissingPermission()
const correctBlocked = computed(() => missing(Permission.RECEIVE_DELIVERIES))

function openCorrection(record: DeliveryRecord, mode: CorrectionMode): void {
  correctionTarget.value = record
  correctionMode.value = mode
  showCorrectDialog.value = true
}

// Pictures of the rows, such as photos of damaged goods: order files that
// name their delivery row, uploaded by the receiver.
const toast = useAppToast()
const { picturesOf, pictures, load, upload, remove } = useDeliveryPictures(
  toRef(() => props.item?.order_id ?? null),
)
const PICTURE_TYPES = 'image/jpeg,image/png,image/webp'
const pictureInput = ref<HTMLInputElement | null>(null)
const pictureTarget = ref<DeliveryRecord | null>(null)
const uploadingFor = ref<number | null>(null)
const thumbnails = ref<Map<number, string>>(new Map())

watch(
  () => props.visible,
  (val) => {
    if (val) void load()
  },
  { immediate: true },
)

async function loadThumbnail(file: OrderFile): Promise<void> {
  if (thumbnails.value.has(file.id)) return
  try {
    const url = URL.createObjectURL(await getOrderFileBlob(file.order_id, file.id))
    thumbnails.value = new Map(thumbnails.value).set(file.id, url)
  } catch {
    /* the picture shows as an icon */
  }
}

watch(
  pictures,
  (list) => {
    for (const file of list) void loadThumbnail(file)
  },
  { immediate: true },
)

onBeforeUnmount(() => thumbnails.value.forEach((url) => URL.revokeObjectURL(url)))

function openPicture(file: OrderFile): void {
  const url = thumbnails.value.get(file.id)
  if (url) window.open(url, '_blank', 'noopener')
}

function pickPicture(record: DeliveryRecord): void {
  pictureTarget.value = record
  pictureInput.value?.click()
}

async function onPicturePicked(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  input.value = ''
  const record = pictureTarget.value
  if (!props.item || !record || files.length === 0) return
  uploadingFor.value = record.id
  try {
    const failed = await upload(props.item.id, record.id, files)
    if (failed > 0) {
      toast.error(
        t('orders.items.deliveryHistory.title'),
        t('orders.items.deliveryHistory.pictureFailed'),
      )
    }
  } finally {
    uploadingFor.value = null
  }
}

async function removePicture(file: OrderFile): Promise<void> {
  try {
    await remove(file.id)
  } catch (e) {
    toast.error(t('orders.items.deliveryHistory.title'), String(e))
  }
}
const { copyToClipboard } = useClipboard()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const cm = ref()
const contextMenuItem = ref<DeliveryRecord | null>(null)

function reasonLabel(reason: string | null): string {
  return reason ? t(scrapReasonLabelKey(reason as ScrapReason)) : getEmptyPlaceholder()
}

function outcomeLabel(outcome: string | null): string {
  if (outcome === 'redeliver') return t('orders.delivery.reject.outcomeOptions.redeliver')
  if (outcome === 'lost') return t('orders.delivery.reject.outcomeOptions.lost')
  return getEmptyPlaceholder()
}

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  cm.value?.show(event.originalEvent)
}

const contextMenuItems = computed<MenuItem[]>(() => {
  const record = contextMenuItem.value
  if (!record) return []

  return [
    {
      label: t('common.copyUuid'),
      icon: 'mdi mdi-content-copy',
      command: () => void copyToClipboard(record.public_id),
    },
  ]
})
</script>

<template>
  <Dialog
    :visible="visible"
    @update:visible="emit('update:visible', $event)"
    modal
    :header="t('orders.items.deliveryHistory.title')"
    :style="{ width: 'var(--dialog-width-lg)' }"
  >
    <DataTable
      :value="props.item?.delivery_records ?? []"
      v-model:context-menu-selection="contextMenuItem"
      size="small"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
      @row-contextmenu="onRowContextMenu"
    >
      <template #empty>
        <EmptyState :message="t('orders.items.deliveryHistory.empty')" />
      </template>
      <Column field="delivery_date" :header="t('orders.items.deliveryHistory.columns.date')">
        <!-- This dialog IS the arrival audit trail, so it shows the time each
             shipment was booked in, not just the day, and who received it. -->
        <template #body="{ data }: { data: DeliveryRecord }">
          <UserDateCell :date="data.delivery_date" :user="data.receiver" with-time />
        </template>
      </Column>
      <Column field="quantity" :header="t('orders.items.deliveryHistory.columns.quantity')">
        <template #body="{ data }: { data: DeliveryRecord }">
          <span class="quantity-cell">
            {{ data.quantity }} {{ formatUnit(props.item?.unit) }}
            <i
              v-if="data.damage_noted_on_delivery_note"
              class="mdi mdi-truck-alert-outline damage-noted"
              role="img"
              :aria-label="t('orders.items.deliveryHistory.damageNoted')"
              v-tooltip.top="t('orders.items.deliveryHistory.damageNoted')"
              data-testid="damage-noted"
            />
          </span>
        </template>
      </Column>
      <Column
        field="storage_place"
        :header="t('orders.items.deliveryHistory.columns.storagePlace')"
      >
        <template #body="{ data }">{{ data.storage_place ?? getEmptyPlaceholder() }}</template>
      </Column>
      <Column
        field="quantity_rejected"
        :header="t('orders.items.deliveryHistory.columns.rejectedQuantity')"
      >
        <template #body="{ data }: { data: DeliveryRecord }">{{
          data.quantity_rejected > 0
            ? `${data.quantity_rejected} ${formatUnit(props.item?.unit)}`
            : getEmptyPlaceholder()
        }}</template>
      </Column>
      <Column :header="t('orders.items.deliveryHistory.columns.rejectionReason')">
        <template #body="{ data }: { data: DeliveryRecord }">{{
          reasonLabel(data.rejection_reason)
        }}</template>
      </Column>
      <Column :header="t('orders.items.deliveryHistory.columns.rejectionOutcome')">
        <template #body="{ data }: { data: DeliveryRecord }">{{
          outcomeLabel(data.rejection_outcome)
        }}</template>
      </Column>
      <Column :header="t('orders.items.deliveryHistory.columns.correction')">
        <template #body="{ data }: { data: DeliveryRecord }">
          <span v-if="data.corrects_delivery_id" data-testid="correction-reason">{{
            data.correction_reason ??
            (data.quantity_rejected > 0
              ? t('orders.delivery.correct.rejectedAfterReceipt')
              : getEmptyPlaceholder())
          }}</span>
          <span
            v-else-if="correctionOffered(data)"
            class="row-actions"
            v-tooltip.top="correctBlocked || undefined"
          >
            <Button
              icon="mdi mdi-undo-variant"
              size="small"
              severity="warn"
              text
              rounded
              :disabled="!canReceiveDeliveries"
              data-testid="correct-delivery"
              v-tooltip.top="t('orders.delivery.correct.title')"
              :aria-label="t('orders.delivery.correct.title')"
              @click="openCorrection(data, 'miscount')"
            />
            <Button
              icon="mdi mdi-package-variant-remove"
              size="small"
              severity="danger"
              text
              rounded
              :disabled="!canReceiveDeliveries"
              data-testid="report-damage"
              v-tooltip.top="t('orders.delivery.correct.reportDamage')"
              :aria-label="t('orders.delivery.correct.reportDamage')"
              @click="openCorrection(data, 'damage')"
            />
          </span>
          <span v-else>{{ getEmptyPlaceholder() }}</span>
        </template>
      </Column>
      <Column :header="t('orders.items.deliveryHistory.columns.pictures')">
        <template #body="{ data }: { data: DeliveryRecord }">
          <div class="pictures-cell">
            <span
              v-for="file in picturesOf(data.id)"
              :key="file.id"
              class="picture-chip"
              data-testid="delivery-picture"
            >
              <button
                type="button"
                class="picture-thumb"
                :aria-label="t('orders.items.deliveryHistory.openPicture')"
                v-tooltip.top="file.file_name"
                @click="openPicture(file)"
              >
                <img v-if="thumbnails.get(file.id)" :src="thumbnails.get(file.id)" alt="" />
                <i v-else class="mdi mdi-image-outline" aria-hidden="true" />
              </button>
              <Button
                v-if="canReceiveDeliveries"
                icon="mdi mdi-close"
                size="small"
                severity="secondary"
                text
                rounded
                class="picture-remove"
                v-tooltip.top="t('orders.items.deliveryHistory.removePicture')"
                :aria-label="t('orders.items.deliveryHistory.removePicture')"
                @click="removePicture(file)"
              />
            </span>
            <span v-tooltip.top="correctBlocked || undefined">
              <Button
                icon="mdi mdi-camera-plus-outline"
                size="small"
                severity="secondary"
                text
                rounded
                :disabled="!canReceiveDeliveries"
                :loading="uploadingFor === data.id"
                data-testid="add-delivery-picture"
                v-tooltip.top="t('orders.items.deliveryHistory.addPicture')"
                :aria-label="t('orders.items.deliveryHistory.addPicture')"
                @click="pickPicture(data)"
              />
            </span>
          </div>
        </template>
      </Column>
    </DataTable>

    <ContextMenu ref="cm" :model="contextMenuItems" @hide="contextMenuItem = null" />
    <input
      ref="pictureInput"
      type="file"
      class="hidden-input"
      aria-hidden="true"
      tabindex="-1"
      multiple
      :accept="PICTURE_TYPES"
      data-testid="delivery-picture-input"
      @change="onPicturePicked"
    />
    <CorrectDeliveryDialog
      v-model:visible="showCorrectDialog"
      :item="item"
      :record="correctionTarget"
      :initial-mode="correctionMode"
      @corrected="emit('update:visible', false)"
    />
    <template #footer>
      <Button
        :label="t('common.close')"
        severity="secondary"
        outlined
        @click="emit('update:visible', false)"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.quantity-cell {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}

.damage-noted {
  color: var(--p-orange-500);
}

.row-actions {
  display: inline-flex;
  gap: var(--space-1);
}

.pictures-cell {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-1);
}

.picture-chip {
  display: inline-flex;
  align-items: center;
}

.picture-thumb {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  padding: 0;
  overflow: hidden;
  cursor: pointer;
  background: var(--p-content-hover-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.picture-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.picture-remove {
  width: 1.5rem;
  height: 1.5rem;
}

.hidden-input {
  display: none;
}
</style>
