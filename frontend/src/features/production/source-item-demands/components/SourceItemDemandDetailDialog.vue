<script setup lang="ts">
import { computed, defineAsyncComponent, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { hasAction } from '@/core/utils/lifecycleActions'

import { extractApiError } from '@/core/utils/errors'
import {
  DEMAND_STATUS_SEVERITY,
  offeredManualStatuses,
  type ManualDemandStatus,
} from '@/core/utils/demandStatus'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { cancelBlockedReason } from '../utils/sourceItemDemandCancel'
import { useSourceItemsAllocationsStore } from '../stores/sourceItemsAllocationsStore'
import { useDemandEditForm } from '@/shared/composables/useDemandEditForm'
import { useDemandUnitOptions } from '@/shared/composables/useDemandUnitOptions'
import {
  demandCommonEditFieldsFromResponse,
  demandCommonFieldsToPayload,
  type DemandCommonEditFields,
} from '@/shared/utils/demandCommonFields'
import DemandEditFieldsBlock from '@/shared/components/demands/DemandEditFieldsBlock.vue'
import ConfirmActionDialog from '@/shared/components/dialogs/ConfirmActionDialog.vue'
import SourceItemDemandCancelDialog from './SourceItemDemandCancelDialog.vue'

import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { BOUGHT_ITEM_UNIT_CODES, formatUnit } from '@/shared/utils/units'
import { itemSublabel, useSourceItemDemandsStore } from '@/features/source-items'
import type { SourceItemDemandResponse } from '@/features/source-items'

// Loaded on demand because it imports the orders barrel, and the orders
// barrel leads back to the source-items barrel through the made-item
// material source picker. A static import would close an import cycle
// between the feature barrels, which src/__tests__/featureImportCycles.spec.ts
// rejects.
const SourceItemManageAllocationsDialog = defineAsyncComponent(
  () => import('./SourceItemManageAllocationsDialog.vue'),
)

const props = defineProps<{
  demand: SourceItemDemandResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  updated: [demand: SourceItemDemandResponse]
}>()

const { t } = useI18n()
const { toastOnError } = useErrorToast()

const demandsStore = useSourceItemDemandsStore()
const allocationsStore = useSourceItemsAllocationsStore()

function itemArticleName(d: SourceItemDemandResponse): string {
  if (d.bought_item) return d.bought_item.article_name
  if (d.source_item) return d.source_item.dimension || `Source item #${d.source_item.id}`
  return getEmptyPlaceholder()
}

function itemOrderCode(d: SourceItemDemandResponse): string {
  return itemSublabel(d)
}

// ── Edit ──────────────────────────────────────────────────────────────

const autoAllocating = ref(false)
const fulfillingFromStock = ref(false)
const statusChanging = ref(false)
const autoAllocateMessage = ref<string | null>(null)
const fulfillFromStockMessage = ref<string | null>(null)
const fulfillQuantity = ref<number | null>(null)
const showManageAllocations = ref(false)

const summary = computed(() =>
  props.demand ? allocationsStore.getSummary(props.demand.id) : undefined,
)

const unitOptions = useDemandUnitOptions(BOUGHT_ITEM_UNIT_CODES, (code) =>
  t(`boughtItems.units.${code}`),
)

const {
  form: editState,
  saving,
  errorMessage,
  onSave,
} = useDemandEditForm<SourceItemDemandResponse, DemandCommonEditFields>({
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
  }),
  formFromDemand: (d) => demandCommonEditFieldsFromResponse(d),
  onOpen: (demand) => {
    autoAllocateMessage.value = null
    fulfillFromStockMessage.value = null
    fulfillQuantity.value = null
    allocationsStore.fetchSummaries([demand.id]).catch(toastOnError())
  },
  save: (id, fields) => demandsStore.update(id, demandCommonFieldsToPayload(fields)),
  onSaved: (updated) => emit('updated', updated),
  unknownErrorMessage: t('sourceItems.demands.detail.errors.unknown'),
})

// A fulfilled or canceled demand is not edited any more, as its actions say.
const editOffered = computed(() => hasAction(props.demand, 'edit_quantity'))

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
// The cancel route of a raw material demand asks for the lot permission
// instead, as the demands table's cancel action does. Without it the button
// stays visible, disabled with the reason.
const cancelBlocked = computed(() =>
  props.demand ? cancelBlockedReason(props.demand, hasPermission(Permission.WRITE_LOTS)) : '',
)
const cancelBlockedText = computed(() =>
  cancelBlocked.value
    ? t(`sourceItems.demands.detail.cancelBlocked.${cancelBlocked.value}`, {
        lot: props.demand?.lot_number ?? '',
      })
    : '',
)

// Marking the demand fulfilled releases what its order lines have not
// delivered yet, so it asks first.
const showFulfil = ref(false)

function requestStatusChange(newStatus: ManualDemandStatus): void {
  if (newStatus === 'fulfilled') showFulfil.value = true
  else if (newStatus === 'canceled') requestCancel('status')
  else void onStatusChange(newStatus)
}

async function onStatusChange(newStatus: ManualDemandStatus): Promise<void> {
  if (!props.demand) return

  statusChanging.value = true
  errorMessage.value = null

  try {
    const updated = await demandsStore.updateStatus(props.demand.id, newStatus)
    emit('updated', updated)
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t('sourceItems.demands.detail.errors.unknown')
  } finally {
    statusChanging.value = false
  }
}

async function onAutoAllocate(): Promise<void> {
  if (!props.demand) return

  autoAllocating.value = true
  autoAllocateMessage.value = null
  errorMessage.value = null

  try {
    const result = await allocationsStore.autoAllocate(props.demand.id)
    if (result.allocations_created === 0 && result.allocations_updated === 0) {
      autoAllocateMessage.value = t('sourceItems.demands.detail.autoAllocateNone')
    } else {
      autoAllocateMessage.value = t('sourceItems.demands.detail.autoAllocateSuccess', {
        createdPhrase: t(
          'sourceItems.demands.detail.allocationsCountPhrase',
          result.allocations_created,
        ),
        updatedPhrase: t(
          'sourceItems.demands.detail.allocationsCountPhrase',
          result.allocations_updated,
        ),
      })
    }
    if (result.demand_status_changed_to) {
      void demandsStore.refresh()
    }
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t('sourceItems.demands.detail.errors.unknown')
  } finally {
    autoAllocating.value = false
  }
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
    fulfillFromStockMessage.value = t('sourceItems.demands.detail.fulfillFromStockSuccess', {
      quantity: result.quantity_fulfilled,
      unit: summary.value?.unit ?? '',
    })
    fulfillQuantity.value = null
    if (result.demand_status_changed_to) {
      void demandsStore.refresh()
    }
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t('sourceItems.demands.detail.errors.unknown')
  } finally {
    fulfillingFromStock.value = false
  }
}

async function onAllocationsChanged(): Promise<void> {
  if (!props.demand) return
  await allocationsStore.fetchSummaries([props.demand.id])
  void demandsStore.refresh()
}

// Every cancel of a raw material demand asks what becomes of its lot. The
// Cancel Demand button goes through the cancel route, the status button
// through the status route, which manage:demand_items opens.
const showCancelPrompt = ref(false)
const cancelVia = ref<'cancel' | 'status'>('cancel')
const cancelPromptDemands = computed(() => (props.demand ? [props.demand] : []))

function requestCancel(via: 'cancel' | 'status'): void {
  if (!props.demand) return
  cancelVia.value = via
  showCancelPrompt.value = true
}

function onCancelDemand(): void {
  requestCancel('cancel')
}

async function onCancelChosen(cancelLot: boolean): Promise<void> {
  if (!props.demand) return
  errorMessage.value = null
  try {
    const updated =
      cancelVia.value === 'cancel'
        ? await demandsStore.cancel(props.demand.id, cancelLot)
        : await demandsStore.cancelByStatus(props.demand.id, cancelLot)
    emit('updated', updated)
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t('sourceItems.demands.detail.errors.unknown')
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="demand ? t('sourceItems.demands.detail.title', { id: demand.id }) : ''"
    :style="{ width: 'var(--dialog-width-lg)' }"
  >
    <div v-if="demand" class="detail-layout">
      <div class="detail-header">
        <div class="detail-meta">
          <span class="meta-label">{{ t('sourceItems.demands.columns.item') }}</span>
          <span class="meta-value"
            ><strong>{{ itemArticleName(demand) }}</strong></span
          >
          <span class="meta-value">{{ itemOrderCode(demand) }}</span>
        </div>
        <div class="detail-meta">
          <span class="meta-label">{{ t('sourceItems.demands.columns.project') }}</span>
          <span class="meta-value"
            ><strong>{{ demand.project_number }}</strong></span
          >
          <span class="meta-value">{{ demand.project_customer }}</span>
        </div>
        <div class="detail-meta">
          <span class="meta-label">{{ t('sourceItems.demands.columns.status') }}</span>
          <div class="status-buttons">
            <Tag
              :value="t(`sourceItems.demands.status.${demand.status}`)"
              :severity="DEMAND_STATUS_SEVERITY[demand.status]"
            />
            <span
              v-for="status in offeredManualStatuses(demand)"
              :key="status"
              v-tooltip.top="setStatusBlocked || undefined"
            >
              <Button
                :label="t(`sourceItems.demands.status.${status}`)"
                severity="secondary"
                outlined
                size="small"
                :loading="statusChanging"
                :disabled="!canSetStatus || statusChanging"
                @click="requestStatusChange(status)"
              />
            </span>
          </div>
        </div>
        <div class="detail-meta">
          <span class="meta-label">{{ t('sourceItems.demands.columns.creator') }}</span>
          <span class="meta-value">{{ demand.creator?.full_name }}</span>
        </div>
      </div>

      <Divider />

      <div class="detail-body">
        <!-- Edit form -->
        <div class="edit-section">
          <div class="section-title">{{ t('sourceItems.demands.detail.editTitle') }}</div>
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
              i18n-prefix="sourceItems.demands.detail"
              id-prefix="bidd"
            />
          </div>
        </div>

        <!-- Allocation summary -->
        <div class="allocation-section">
          <div class="section-title">{{ t('sourceItems.demands.detail.allocationSummary') }}</div>

          <template v-if="summary">
            <Message v-if="summary.unit_mismatch" severity="warn" :closable="false">{{ t('procurement.unitMismatchSummary') }}</Message>
            <div class="summary-grid">
              <div class="summary-row">
                <span class="summary-label">{{ t('sourceItems.demands.detail.total') }}</span>
                <span class="summary-value"
                  >{{ summary.total }} {{ formatUnit(summary.unit) }}</span
                >
              </div>
              <div class="summary-row">
                <span class="summary-label">{{ t('sourceItems.demands.detail.unallocated') }}</span>
                <span class="summary-value" :class="{ 'summary-warning': summary.unallocated > 0 }"
                  >{{ summary.unallocated }} {{ formatUnit(summary.unit) }}</span
                >
              </div>
              <div class="summary-row">
                <span class="summary-label">{{ t('sourceItems.demands.detail.allocated') }}</span>
                <span class="summary-value summary-allocated"
                  >{{ summary.allocated }} {{ formatUnit(summary.unit) }}</span
                >
              </div>
              <div class="summary-row">
                <span class="summary-label">{{ t('sourceItems.demands.detail.inTransit') }}</span>
                <span class="summary-value summary-transit"
                  >{{ summary.in_transit }} {{ formatUnit(summary.unit) }}</span
                >
              </div>
              <div class="summary-row">
                <span class="summary-label">{{ t('sourceItems.demands.detail.delivered') }}</span>
                <span class="summary-value summary-delivered"
                  >{{ summary.delivered }} {{ formatUnit(summary.unit) }}</span
                >
              </div>
              <div v-if="summary.fulfilled_from_stock > 0" class="summary-row">
                <span class="summary-label">{{
                  t('sourceItems.demands.detail.fulfilledFromStock')
                }}</span>
                <span class="summary-value summary-stock"
                  >{{ summary.fulfilled_from_stock }} {{ formatUnit(summary.unit) }}</span
                >
              </div>
              <div v-if="summary.is_fully_allocated" class="summary-badge">
                <Tag
                  :value="t('sourceItems.demands.detail.fullyAllocated')"
                  severity="success"
                  icon="mdi mdi-check"
                />
              </div>
            </div>

            <!-- Substitutions -->
            <div v-if="summary.substitutions?.length" class="subst-section">
              <div class="subst-section-title">
                <i class="mdi mdi-swap-horizontal" aria-hidden="true" />
                {{ t('sourceItems.demands.substitution.sectionTitle') }}
              </div>
              <div
                v-for="sub in summary.substitutions"
                :key="sub.substitute_source_item_id"
                class="subst-row"
              >
                <div class="subst-row-item">
                  <span class="subst-row-code">{{ sub.substitute_item_order_code_1 }}</span>
                  <span class="subst-row-name">{{ sub.substitute_item_article_name }}</span>
                </div>
                <span class="subst-row-qty">{{ sub.quantity }} {{ formatUnit(summary.unit) }}</span>
                <span v-if="sub.substitute_reason" class="subst-row-reason">
                  "{{ sub.substitute_reason }}"
                </span>
              </div>
            </div>
          </template>

          <div v-else class="summary-loading">
            <i class="mdi mdi-loading mdi-spin" aria-hidden="true" />
          </div>

          <div class="allocation-buttons">
            <Button
              :label="t('sourceItems.demands.detail.autoAllocate')"
              icon="mdi mdi-auto-fix"
              severity="contrast"
              outlined
              :loading="autoAllocating"
              class="auto-allocate-btn"
              @click="onAutoAllocate"
            />

            <Button
              :label="t('sourceItems.demands.detail.manageAllocations')"
              icon="mdi mdi-sitemap"
              severity="contrast"
              outlined
              class="manage-allocations-btn"
              @click="showManageAllocations = true"
            />
          </div>

          <Message v-if="autoAllocateMessage" severity="info" :closable="false" class="alloc-msg">
            {{ autoAllocateMessage }}
          </Message>

          <div class="stock-fulfill-row">
            <InputNumber
              v-model="fulfillQuantity"
              :min="0.001"
              :max="summary?.unallocated ?? undefined"
              :max-fraction-digits="3"
              :placeholder="t('sourceItems.demands.detail.fulfillFromStockPlaceholder')"
              fluid
            />
            <Button
              :label="t('sourceItems.demands.detail.fulfillFromStock')"
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

          <span v-tooltip.top="cancelBlockedText" class="cancel-wrap">
            <Button
              :label="t('sourceItems.demands.detail.cancelDemand')"
              icon="mdi mdi-close-circle-outline"
              severity="danger"
              outlined
              class="cancel-btn"
              :disabled="cancelBlocked !== ''"
              data-testid="cancel-demand"
              @click="onCancelDemand"
            />
          </span>
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

  <ConfirmActionDialog
    v-model:visible="showFulfil"
    :header="t('sourceItems.demands.contextMenu.fulfilHeader')"
    :message="t('sourceItems.demands.contextMenu.fulfilConfirm', { count: 1 }, 1)"
    :confirm-label="t('sourceItems.demands.contextMenu.fulfilAction')"
    confirm-severity="primary"
    @confirm="onStatusChange('fulfilled')"
  />

  <SourceItemDemandCancelDialog
    v-model:visible="showCancelPrompt"
    :demands="cancelPromptDemands"
    @confirm="onCancelChosen"
  />

  <SourceItemManageAllocationsDialog
    v-if="demand"
    v-model:visible="showManageAllocations"
    :demand-id="demand.id"
    :demand-unit="demand.unit"
    :bought-item-id="demand.bought_item_id"
    :source-item-id="demand.source_item_id"
    :project-id="demand.project_id"
    :item-article-name="itemArticleName(demand)"
    :item-order-code="itemOrderCode(demand)"
    @changed="onAllocationsChanged"
  />
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

.edit-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-3);
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

.summary-allocated {
  color: var(--p-blue-500);
}

.summary-warning {
  color: var(--p-orange-500);
  font-weight: 600;
}

.summary-transit {
  color: var(--p-cyan-500);
}

.summary-delivered {
  color: var(--p-green-500);
}

.summary-stock {
  color: var(--p-purple-500);
}

.summary-badge {
  margin-top: var(--space-1);
}

.subst-section {
  margin-top: var(--space-2);
  margin-bottom: var(--space-3);
  padding: var(--space-2) var(--space-2);
  border: 1px solid var(--p-primary-200, var(--p-primary-color));
  border-radius: var(--p-content-border-radius);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  opacity: 0.9;
}

.subst-section-title {
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--p-primary-color);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.subst-row {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.subst-row-item {
  display: flex;
  flex-direction: column;
}

.subst-row-code {
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.subst-row-name {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.subst-row-qty {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.subst-row-reason {
  font-size: var(--font-size-xs);
  font-style: italic;
  color: var(--p-text-muted-color);
}

.summary-loading {
  display: flex;
  justify-content: center;
  padding: var(--space-4);
  color: var(--p-text-muted-color);
}

.allocation-buttons {
  display: flex;
  flex-direction: row;
  gap: var(--space-2);
  padding-bottom: var(--space-2);
}

.auto-allocate-btn {
  width: 100%;
}

.stock-fulfill-row {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-2);

  :deep(.p-inputnumber) {
    flex: 1;
  }
}

.alloc-msg {
  margin-bottom: var(--space-2);
}

.manage-allocations-btn {
  width: 100%;
}

.cancel-wrap {
  display: block;
  margin-top: var(--space-2);
}

.cancel-btn {
  width: 100%;
}

.error-msg {
  margin-top: var(--space-2);
}

.status-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
</style>
