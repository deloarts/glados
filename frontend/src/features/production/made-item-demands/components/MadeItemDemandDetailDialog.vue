<script setup lang="ts">
import { extractApiError } from '@/core/utils/errors'
import { computed, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { hasAction } from '@/core/utils/lifecycleActions'

import { useMadeItemsAllocationsStore } from '../stores/madeItemsAllocationsStore'
import {
  DEMAND_STATUS_SEVERITY,
  offeredManualStatuses,
  type ManualDemandStatus,
} from '@/core/utils/demandStatus'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import LotCreateDialog from '../../lots/components/LotCreateDialog.vue'
import { useLotNumberCache } from '../../lots/composables/useLotNumberCache'
import { useLotDetail } from '@/shared/composables/useLotDetail'
import MadeItemDemandCancelDialog from './MadeItemDemandCancelDialog.vue'
import { useDemandEditForm } from '@/shared/composables/useDemandEditForm'
import { useDemandUnitOptions } from '@/shared/composables/useDemandUnitOptions'
import {
  demandCommonEditFieldsFromResponse,
  demandCommonFieldsToPayload,
  type DemandCommonEditFields,
} from '@/shared/utils/demandCommonFields'
import DemandEditFieldsBlock from '@/shared/components/demands/DemandEditFieldsBlock.vue'

import { BOUGHT_ITEM_UNIT_CODES, formatUnit } from '@/shared/utils/units'
import {
  useMadeItemsDemandsStore,
  useMadeItemsStore,
  getMadeItems,
  useMadeItemLabel,
  MadeItemSelect,
} from '@/features/made-items'
import type { MadeItemDemandResponse, MadeItemResponse } from '@/features/made-items'

const props = defineProps<{
  demand: MadeItemDemandResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  updated: [item: MadeItemDemandResponse]
}>()

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const { format: madeItemLabel } = useMadeItemLabel()

const demandsStore = useMadeItemsDemandsStore()
const allocationsStore = useMadeItemsAllocationsStore()
const madeItemsStore = useMadeItemsStore()

interface EditFields extends DemandCommonEditFields {
  is_alteration: boolean
  alteration_of_item: MadeItemResponse | null
}

const fulfillingFromStock = ref(false)
const savingStockAllocation = ref(false)
const statusChanging = ref(false)
const fulfillFromStockMessage = ref<string | null>(null)
const fulfillQuantity = ref<number | null>(null)
const stockAllocationQuantity = ref<number | null>(null)
const showCreateLot = ref(false)

const lotNumberCache = useLotNumberCache()
const { openLotDetail } = useLotDetail()

const summary = computed(() =>
  props.demand ? allocationsStore.getSummary(props.demand.id) : undefined,
)

watch(summary, (value) => {
  for (const lotId of value?.lot_ids ?? []) {
    lotNumberCache.ensureLoaded(lotId)
  }
})

const currentStockAllocation = computed(() => {
  if (!props.demand) return undefined
  return allocationsStore.getAllocations(props.demand.id).find((a) => a.source === 'stock')
})

const unitOptions = useDemandUnitOptions(BOUGHT_ITEM_UNIT_CODES, (code) =>
  t(`boughtItems.units.${code}`),
)

async function loadAlterationItem(id: number, fields: EditFields): Promise<void> {
  const cached = madeItemsStore.getById(id)
  if (cached) {
    fields.alteration_of_item = cached
    return
  }

  const result = await getMadeItems({ id, limit: 1 })
  if (result.items[0]) {
    fields.alteration_of_item = result.items[0]
  }
}

const {
  form: editState,
  saving,
  errorMessage,
  onSave,
} = useDemandEditForm<MadeItemDemandResponse, EditFields>({
  visible,
  demand: () => props.demand,
  emptyForm: () => ({
    quantity: 0,
    unit: '',
    items_per_unit: 1,
    high_priority: false,
    notify_on_delivery: false,
    desired_delivery_date: null,
    note: '',
    is_alteration: false,
    alteration_of_item: null,
  }),
  formFromDemand: (d) => ({
    ...demandCommonEditFieldsFromResponse(d),
    is_alteration: d.is_alteration,
    alteration_of_item: null,
  }),
  onOpen: async (demand, fields) => {
    fulfillFromStockMessage.value = null
    fulfillQuantity.value = null
    const tasks: Promise<unknown>[] = [
      allocationsStore.fetchSummaries([demand.id]),
      allocationsStore.fetchAllocations(demand.id),
    ]
    if (demand.is_alteration && demand.alteration_of_made_item_id) {
      tasks.push(loadAlterationItem(demand.alteration_of_made_item_id, fields))
    }
    await Promise.all(tasks)
    stockAllocationQuantity.value = currentStockAllocation.value?.quantity ?? null
  },
  save: (id, fields) =>
    demandsStore.update(id, {
      ...demandCommonFieldsToPayload(fields),
      is_alteration: fields.is_alteration,
      alteration_of_made_item_id: fields.is_alteration ? (fields.alteration_of_item?.id ?? null) : null,
    }),
  onSaved: (updated) => emit('updated', updated),
  unknownErrorMessage: t('madeItems.demands.detail.errors.unknown'),
})

// A fulfilled or canceled demand is not edited any more, as its actions say.
const editOffered = computed(() => hasAction(props.demand, 'edit_quantity'))

watch(
  () => editState.is_alteration,
  (isAlteration) => {
    if (!isAlteration) {
      editState.alteration_of_item = null
    }
  },
)

const showCancel = ref(false)

const { hasPermission } = usePermissions()
// Both statuses a user sets are irreversible, so the backend's demand
// status rule reserves them for holders of write:demand_items and
// manage:demand_items, and a fulfilled or canceled demand takes neither.
const canSetStatus = computed(
  () =>
    hasPermission(Permission.WRITE_DEMAND_ITEMS) && hasPermission(Permission.MANAGE_DEMAND_ITEMS),
)
// The demand's state decides which statuses are offered; without both
// permissions they stay visible but disabled, naming the missing one.
const { missing } = useMissingPermission()
const setStatusBlocked = computed(() =>
  missing(Permission.WRITE_DEMAND_ITEMS, Permission.MANAGE_DEMAND_ITEMS),
)

async function onStatusChange(newStatus: ManualDemandStatus): Promise<void> {
  if (!props.demand) return

  // Canceling cascades into lots, production orders, supplier order items
  // and raw-material demands, always via the impact dialog, never as a
  // one-click status flip.
  if (newStatus === 'canceled') {
    showCancel.value = true
    return
  }

  statusChanging.value = true
  errorMessage.value = null

  try {
    const updated = await demandsStore.updateStatus(props.demand.id, newStatus)
    emit('updated', updated)
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t('madeItems.demands.detail.errors.unknown')
  } finally {
    statusChanging.value = false
  }
}

/**
 * The cancel dialog performs the cascade itself; the demand row in the
 * store is already updated, so this only has to propagate it upward.
 */
function onCanceled(): void {
  const canceled = demandsStore.items.find((item) => item.id === props.demand?.id)
  if (canceled) emit('updated', canceled)
}

const canFulfillFromStock = computed(
  () =>
    !!fulfillQuantity.value &&
    fulfillQuantity.value > 0 &&
    (!summary.value || fulfillQuantity.value <= summary.value.unallocated),
)

async function onFulfillFromStock(): Promise<void> {
  if (!props.demand || !fulfillQuantity.value) return

  fulfillingFromStock.value = true
  fulfillFromStockMessage.value = null
  errorMessage.value = null

  try {
    const result = await allocationsStore.fulfillFromStock(props.demand.id, fulfillQuantity.value)
    fulfillFromStockMessage.value = t('madeItems.demands.detail.fulfillFromStockSuccess', {
      quantity: result.quantity_fulfilled,
      unit: summary.value?.unit ?? '',
    })
    fulfillQuantity.value = null
    stockAllocationQuantity.value = currentStockAllocation.value?.quantity ?? null
    if (result.demand_status_changed_to) {
      void demandsStore.refresh()
    }
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t('madeItems.demands.detail.errors.unknown')
  } finally {
    fulfillingFromStock.value = false
  }
}

async function onSaveStockAllocation(): Promise<void> {
  if (!props.demand || stockAllocationQuantity.value === null) return

  savingStockAllocation.value = true
  errorMessage.value = null

  try {
    await allocationsStore.updateStockAllocation(props.demand.id, stockAllocationQuantity.value)
    void demandsStore.refresh()
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t('madeItems.demands.detail.errors.unknown')
  } finally {
    savingStockAllocation.value = false
  }
}

async function onClearStockAllocation(): Promise<void> {
  if (!props.demand) return

  savingStockAllocation.value = true
  errorMessage.value = null

  try {
    await allocationsStore.deleteStockAllocation(props.demand.id)
    stockAllocationQuantity.value = null
    void demandsStore.refresh()
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t('madeItems.demands.detail.errors.unknown')
  } finally {
    savingStockAllocation.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="demand ? t('madeItems.demands.detail.title', { id: demand.id }) : ''"
    :style="{ width: 'var(--dialog-width-lg)' }"
  >
    <div v-if="demand" class="detail-layout">
      <!-- Header info -->
      <div class="detail-header">
        <div class="detail-meta">
          <span class="meta-label">{{ t('madeItems.demands.columns.item') }}</span>
          <span class="meta-value"
            ><strong>{{ demand.item_article_name }}</strong></span
          >
          <span class="meta-value">
            {{ madeItemLabel(demand.item_part_number, demand.item_revision) }}
          </span>
        </div>
        <div class="detail-meta">
          <span class="meta-label">{{ t('madeItems.demands.columns.project') }}</span>
          <span class="meta-value">
            <strong>{{ demand.project_number }}</strong>
          </span>
          <span class="meta-value">{{ demand.project_customer }}</span>
          <span class="meta-value">{{ demand.project_description }}</span>
        </div>
        <div class="detail-meta">
          <span class="meta-label">{{ t('madeItems.demands.columns.status') }}</span>
          <div class="status-buttons">
            <Tag
              :value="t(`madeItems.demands.status.${demand.status}`)"
              :severity="DEMAND_STATUS_SEVERITY[demand.status]"
            />
            <span
              v-for="status in offeredManualStatuses(demand)"
              :key="status"
              v-tooltip.top="setStatusBlocked || undefined"
            >
              <Button
                :label="t(`madeItems.demands.status.${status}`)"
                severity="secondary"
                outlined
                size="small"
                :loading="statusChanging"
                :disabled="!canSetStatus || statusChanging"
                @click="onStatusChange(status)"
              />
            </span>
          </div>
        </div>
        <div class="detail-meta">
          <span class="meta-label">{{ t('madeItems.demands.columns.creator') }}</span>
          <span class="meta-value">{{ demand.creator?.full_name }}</span>
        </div>
        <div v-if="demand.is_alteration" class="detail-meta">
          <span class="meta-label">{{ t('madeItems.demands.detail.fields.isAlteration') }}</span>
          <span class="meta-value">
            <Tag
              :value="`${madeItemLabel(
                demand.alteration_of_made_item_part_number,
                demand.alteration_of_made_item_revision,
              )} - ${demand.alteration_of_made_item_article_name}`"
              severity="warn"
              icon="mdi mdi-wrench"
            />
          </span>
        </div>
      </div>

      <Divider />

      <!-- Two-column layout: edit form + allocation -->
      <div class="detail-body">
        <!-- Edit form -->
        <div class="edit-section">
          <div class="section-title">{{ t('madeItems.demands.detail.editTitle') }}</div>
          <div class="edit-grid">
            <DemandEditFieldsBlock
              v-model:quantity="editState.quantity"
              v-model:unit="editState.unit"
              v-model:items-per-unit="editState.items_per_unit"
              v-model:high-priority="editState.high_priority"
              v-model:notify-on-delivery="editState.notify_on_delivery"
              v-model:desired-delivery-date="editState.desired_delivery_date"
              v-model:note="editState.note"
              :unit-options="unitOptions"
              i18n-prefix="madeItems.demands.detail"
              id-prefix="made-detail"
            >
              <template #extra-fields>
                <div class="field checkbox-field field-wide">
                  <Checkbox
                    v-model="editState.is_alteration"
                    input-id="made-detail-is-alteration"
                    :binary="true"
                  />
                  <label for="made-detail-is-alteration">{{
                    t('madeItems.demands.detail.fields.isAlteration')
                  }}</label>
                </div>
                <div v-if="editState.is_alteration" class="field field-wide">
                  <label :id="`${uid}-alteration-of-item-label`" :for="`${uid}-alteration-of-item`">
                    {{ t('madeItems.demands.detail.fields.alterationOfItem') }}
                  </label>
                  <MadeItemSelect
                    v-model="editState.alteration_of_item"
                    :input-id="`${uid}-alteration-of-item`"
                    :aria-labelledby="`${uid}-alteration-of-item-label`"
                    :exclude-id="demand.made_item_id"
                    fluid
                  />
                </div>
              </template>
            </DemandEditFieldsBlock>
          </div>
        </div>

        <!-- Allocation summary -->
        <div class="allocation-section">
          <div class="section-title">{{ t('madeItems.demands.detail.allocationSummary') }}</div>

          <template v-if="summary">
            <div class="summary-grid">
              <div class="summary-row">
                <span class="summary-label">{{ t('madeItems.demands.detail.total') }}</span>
                <span class="summary-value"
                  >{{ summary.total }} {{ formatUnit(summary.unit) }}</span
                >
              </div>
              <div class="summary-row">
                <span class="summary-label">{{ t('madeItems.demands.detail.unallocated') }}</span>
                <span class="summary-value" :class="{ 'summary-warning': summary.unallocated > 0 }"
                  >{{ summary.unallocated }} {{ formatUnit(summary.unit) }}</span
                >
              </div>
              <div class="summary-row">
                <span class="summary-label">{{
                  t('madeItems.demands.detail.fulfilledFromStock')
                }}</span>
                <span class="summary-value summary-stock"
                  >{{ summary.fulfilled_from_stock }} {{ formatUnit(summary.unit) }}</span
                >
              </div>
              <div v-if="summary.is_fully_allocated" class="summary-badge">
                <Tag
                  :value="t('madeItems.demands.detail.fullyAllocated')"
                  severity="success"
                  icon="mdi mdi-check"
                />
              </div>
            </div>
          </template>

          <div v-else class="summary-loading">
            <i class="mdi mdi-loading mdi-spin" aria-hidden="true" />
          </div>

          <!-- Lots -->
          <div class="section-title stock-alloc-title">
            {{ t('madeItems.demands.detail.lots') }}
          </div>
          <div class="lots-row">
            <template v-if="summary?.lot_ids?.length">
              <a
                v-for="lotId in summary.lot_ids ?? []"
                :key="lotId"
                class="lot-tag-link"
                role="button"
                tabindex="0"
                @click="openLotDetail(lotId)"
                @keydown.enter="openLotDetail(lotId)"
              >
                <Tag :value="lotNumberCache.lotNumber(lotId)" severity="secondary" />
              </a>
            </template>
            <span v-else class="muted">{{ t('madeItems.demands.detail.noLots') }}</span>
            <Button
              :label="t('madeItems.demands.detail.createLot')"
              icon="mdi mdi-factory"
              size="small"
              severity="secondary"
              outlined
              @click="showCreateLot = true"
            />
          </div>

          <!-- Direct stock-allocation edit -->
          <div class="section-title stock-alloc-title">
            {{ t('madeItems.demands.detail.stockAllocation') }}
          </div>
          <div class="stock-alloc-row">
            <InputNumber
              class="row-input"
              v-model="stockAllocationQuantity"
              :min="0"
              :max="summary?.total ?? undefined"
              :max-fraction-digits="0"
              :placeholder="t('madeItems.demands.detail.fulfillFromStockPlaceholder')"
              fluid
            />
            <Button
              icon="mdi mdi-content-save-outline"
              severity="contrast"
              outlined
              :loading="savingStockAllocation"
              :disabled="stockAllocationQuantity === null"
              v-tooltip.focus="t('common.save')"
              :aria-label="t('common.save')"
              @click="onSaveStockAllocation"
            />
            <Button
              icon="mdi mdi-close"
              severity="danger"
              outlined
              :loading="savingStockAllocation"
              :disabled="!currentStockAllocation"
              v-tooltip.focus="t('common.clear')"
              :aria-label="t('common.clear')"
              @click="onClearStockAllocation"
            />
          </div>

          <div class="stock-fulfill-row">
            <InputNumber
              class="row-input"
              v-model="fulfillQuantity"
              :min="1"
              :max="summary?.unallocated ?? undefined"
              :max-fraction-digits="0"
              :placeholder="t('madeItems.demands.detail.fulfillFromStockPlaceholder')"
              fluid
            />
            <Button
              :label="t('madeItems.demands.detail.fulfillFromStock')"
              icon="mdi mdi-package-variant-closed"
              severity="contrast"
              outlined
              :loading="fulfillingFromStock"
              :disabled="!canFulfillFromStock"
              @click="onFulfillFromStock"
            />
          </div>

          <Message
            v-if="fulfillFromStockMessage"
            severity="info"
            :closable="false"
            class="alloc-msg"
          >
            {{ fulfillFromStockMessage }}
          </Message>
        </div>
      </div>

      <Message v-if="errorMessage" severity="error" :closable="false" class="error-msg">
        {{ errorMessage }}
      </Message>
    </div>

    <template #footer>
      <Button :label="t('common.cancel')" severity="secondary" outlined :disabled="saving" @click="visible = false" />
      <Button :label="t('common.save')" :loading="saving" :disabled="!editOffered" @click="onSave" />
    </template>
  </Dialog>

  <LotCreateDialog
    v-model:visible="showCreateLot"
    :preset-item="demand?.item ?? null"
    :preset-demand="demand"
    @created="() => demand && allocationsStore.fetchSummaries([demand.id])"
  />

  <MadeItemDemandCancelDialog v-model:visible="showCancel" :demand="demand" @canceled="onCanceled" />
</template>

<style scoped lang="scss">
.detail-layout {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.detail-header {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-2) var(--space-5);
}

.detail-meta {
  padding-top: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.meta-label {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.meta-value {
  font-size: var(--font-size-sm);
}

.detail-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-5);
}

.section-title {
  font-weight: 600;
  font-size: var(--font-size-sm);
  margin-bottom: var(--space-3);
  color: var(--p-text-color);
}

.stock-alloc-title {
  margin-top: var(--space-4);
}

.edit-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-3);
}

.field {
  label {
    font-size: var(--font-size-sm);
    color: var(--p-text-muted-color);
  }
}

.field-wide {
  grid-column: 1 / -1;
}

.checkbox-field {
  flex-direction: row;
  align-items: center;
  gap: var(--space-2);

  label {
    font-size: var(--font-size-sm);
    color: var(--p-text-color);
  }
}

.summary-grid {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.summary-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: var(--font-size-sm);
}

.summary-label {
  color: var(--p-text-muted-color);
}

.summary-value {
  font-weight: 500;
}

.summary-warning {
  color: var(--p-orange-500);
  font-weight: 600;
}

.summary-stock {
  color: var(--p-purple-500);
}

.summary-badge {
  margin-top: var(--space-1);
}

.summary-loading {
  display: flex;
  justify-content: center;
  padding: var(--space-4);
  color: var(--p-text-muted-color);
}

.stock-alloc-row {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.stock-fulfill-row {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.alloc-msg {
  margin-bottom: var(--space-2);
}

.error-msg {
  margin-top: var(--space-2);
}

.status-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.lots-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.lot-tag-link {
  text-decoration: none;
}

.muted {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.row-input {
  flex: 1;
}
</style>
