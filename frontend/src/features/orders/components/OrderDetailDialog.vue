<script setup lang="ts">
import { extractApiError } from '@/core/utils/errors'
import { formatDateTimeOrDash } from '@/core/utils/dates'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'
import { useAppToast } from '@/core/composables/useAppToast'

import { getOrder } from '../api/getOrder'
import { useOrdersStore } from '../stores/ordersStore'
import { useOrderFormatters } from '../composables/useOrderFormatters'
import { orderActionGates } from '../composables/useOrderItemActions'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import UserAvatarPreview from '@/shared/components/user/UserAvatarPreview.vue'

import OrderItemsTable from './OrderItemsTable.vue'
import OrderItemCreateForm from './OrderItemCreateForm.vue'
import DeliverItemDialog from './DeliverItemDialog.vue'
import DeliveryHistoryDialog from './DeliveryHistoryDialog.vue'

import type { OrderItemResponse, OrderResponse } from '../types/ordersResponse'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { useDialogTarget } from '@/shared/composables/useDialogTarget'

// Its confirm uses a group of its own and mounts the matching ConfirmDialog
// inside the dialog, so the question shows above it wherever it is opened.
const CONFIRM_GROUP = 'order-detail'

const props = defineProps<{
  orderId: number | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const { hasPermission } = usePermissions()
const { orderTotalPrice, orderStatusSeverity } = useOrderFormatters()
const ordersStore = useOrdersStore()
const confirm = useConfirm()
const toast = useAppToast()

const canWrite = computed(() => hasPermission(Permission.WRITE_ORDERS))
const { missing } = useMissingPermission()
const writeBlocked = computed(() => missing(Permission.WRITE_ORDERS))
// An order someone canceled takes no new line, so its actions offer none.
const canAddItem = computed(
  () => order.value !== null && orderActionGates.addItem(order.value, canWrite.value),
)
const canReceiveDeliveries = computed(() => hasPermission(Permission.RECEIVE_DELIVERIES))

const order = ref<OrderResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

async function loadOrder(): Promise<void> {
  if (props.orderId === null) return
  loading.value = true
  error.value = null
  try {
    order.value = await getOrder(props.orderId)
  } catch (e) {
    error.value = extractApiError(e) ?? t('orders.detail.errors.unknown')
  } finally {
    loading.value = false
  }
}

watch(
  () => [visible.value, props.orderId] as const,
  ([isVisible]) => {
    if (isVisible) void loadOrder()
  },
  { immediate: true },
)

function closeAndNavigate(navigate: (event: MouseEvent) => void, event: MouseEvent): void {
  visible.value = false
  navigate(event)
}

// ── Add item dialog ─────────────────────────────────────────────────

const showAddItem = ref(false)
const addItemVirtual = ref(false)

function openAddItem(isVirtual: boolean): void {
  addItemVirtual.value = isVirtual
  showAddItem.value = true
}

const addItemMenuItems = computed(() => [
  {
    label: t('orders.actions.addItemMenu.bought'),
    icon: 'mdi mdi-cart-outline',
    command: () => openAddItem(false),
  },
  {
    label: t('orders.actions.addItemMenu.virtual'),
    icon: 'mdi mdi-file-outline',
    command: () => openAddItem(true),
  },
  {
    label: t('orders.actions.addItemMenu.made'),
    icon: 'mdi mdi-cog-outline',
    disabled: true,
    title: t('orders.actions.addItemMenu.madeComingSoon'),
  },
])

// ── Deliver single item dialog ─────────────────────────────────────

const {
  target: deliverTarget,
  visible: showDeliverDialog,
  open: openDeliverTarget,
} = useDialogTarget<OrderItemResponse>()

// orderId is unused; the dialog knows its order from props.
function openDeliverDialog(_orderId: number, item: OrderItemResponse): void {
  openDeliverTarget(item)
}

watch(showDeliverDialog, (isVisible) => {
  if (!isVisible) void loadOrder()
})

// ── Delivery history dialog ────────────────────────────────────────

const {
  target: historyTarget,
  visible: showHistoryDialog,
  open: openHistoryTarget,
} = useDialogTarget<OrderItemResponse>()

function openHistoryDialog(item: OrderItemResponse): void {
  openHistoryTarget(item)
}

// ── Remove item confirm ─────────────────────────────────────────────

function confirmRemoveItem(_orderId: number, item: OrderItemResponse): void {
  async function onAccept(): Promise<void> {
    if (props.orderId === null) return
    try {
      await ordersStore.removeItem(props.orderId, item.id, item.edit_version)
      await loadOrder()
    } catch (e) {
      toast.error(
        t('orders.actions.removeItem'),
        extractApiError(e) ?? t('orders.detail.errors.unknown'),
      )
    }
  }

  confirm.require({
    group: CONFIRM_GROUP,
    message: t('orders.actions.removeItemConfirm'),
    header: t('orders.actions.removeItemConfirmTitle'),
    icon: 'mdi mdi-delete-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('orders.actions.removeItem'), severity: 'danger' },
    accept: () => void onAccept(),
  })
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="order ? t('orders.detail.title', { number: order.order_number }) : ''"
    :style="{ width: 'var(--dialog-width-full)', height: '85vh' }"
    :content-style="{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }"
  >
    <!-- Replaces the native close button, since OpenVue has no slot for an
         extra header icon. -->
    <template #closebutton="{ closeCallback }">
      <RouterLink v-if="order" v-slot="{ navigate }" :to="`/procurement/orders/${order.id}`" custom>
        <Button
          icon="mdi mdi-open-in-new"
          size="small"
          severity="secondary"
          text
          rounded
          v-tooltip.bottom.focus="t('orders.actions.open')"
          :aria-label="t('orders.actions.open')"
          @click="closeAndNavigate(navigate, $event)"
        />
      </RouterLink>
      <Button
        icon="mdi mdi-close"
        size="small"
        severity="secondary"
        text
        rounded
        v-tooltip.bottom.focus="t('common.close')"
        :aria-label="t('common.close')"
        @click="closeCallback"
      />
    </template>

    <div v-if="loading" class="detail-loading">
      <i class="mdi mdi-loading mdi-spin" aria-hidden="true" />
    </div>
    <Message v-else-if="error" severity="error" :closable="false">{{ error }}</Message>
    <div v-else-if="order" class="detail-layout">
      <div class="detail-header">
        <div class="detail-meta">
          <span class="meta-label">{{ t('orders.columns.status') }}</span>
          <Tag
            :value="t(`orders.status.${order.status}`)"
            :severity="orderStatusSeverity(order.status)"
          />
        </div>
        <div class="detail-meta">
          <span class="meta-label">{{ t('orders.columns.supplier') }}</span>
          <span class="meta-value"
            ><strong>{{ order.supplier_name }}</strong></span
          >
        </div>
        <div class="detail-meta">
          <span class="meta-label">{{ t('orders.columns.totalPrice') }}</span>
          <span class="meta-value">{{ orderTotalPrice(order) }}</span>
        </div>
        <div class="detail-meta">
          <span class="meta-label">{{ t('orders.columns.orderedDate') }}</span>
          <span class="meta-value">{{ formatDateTimeOrDash(order.ordered_date) }}</span>
        </div>
        <div class="detail-meta">
          <span class="meta-label">{{ t('orders.columns.expectedDelivery') }}</span>
          <span class="meta-value">{{
            order.expected_delivery_date ?? getEmptyPlaceholder()
          }}</span>
        </div>
        <div class="detail-meta">
          <span class="meta-label">{{ t('orders.columns.storagePlace') }}</span>
          <span class="meta-value">{{ order.storage_place ?? getEmptyPlaceholder() }}</span>
        </div>
        <div class="detail-meta">
          <span class="meta-label">{{ t('orders.columns.creator') }}</span>
          <UserAvatarPreview :user="order.creator" />
        </div>
        <div v-if="order.note" class="detail-meta detail-meta-wide">
          <span class="meta-label">{{ t('orders.columns.note') }}</span>
          <span class="meta-value">{{ order.note }}</span>
        </div>
      </div>

      <Divider />

      <div class="detail-items-header">
        <span class="section-title">{{ t('orders.items.title') }}</span>
        <div class="detail-items-actions">
          <span v-tooltip.top="writeBlocked || undefined">
            <SplitButton
              :label="t('orders.actions.addItem')"
              icon="mdi mdi-plus"
              size="small"
              severity="secondary"
              text
              :disabled="!canAddItem"
              :model="addItemMenuItems"
              data-testid="order-detail-add-item"
              @click="openAddItem(false)"
            >
              <template #item="{ item, props: itemProps }">
                <a v-bind="itemProps.action" v-tooltip.left="item.disabled ? item.title : undefined">
                  <span v-if="item.icon" :class="item.icon" />
                  <span>{{ item.label }}</span>
                </a>
              </template>
            </SplitButton>
          </span>
        </div>
      </div>

      <div class="items-scroll-container">
        <OrderItemsTable
          :order="order"
          :can-write="canWrite"
          :can-receive-deliveries="canReceiveDeliveries"
          @deliver="openDeliverDialog"
          @remove="confirmRemoveItem"
          @view-history="openHistoryDialog"
          @updated="loadOrder"
        />
      </div>
    </div>
  </Dialog>

  <ConfirmDialog :group="CONFIRM_GROUP" />

  <OrderItemCreateForm
    v-if="order"
    v-model:visible="showAddItem"
    :order-id="order.id"
    :supplier-id="order.supplier_id"
    :initial-virtual="addItemVirtual"
    @created="loadOrder"
  />

  <DeliverItemDialog
    v-model:visible="showDeliverDialog"
    :order-id="order?.id ?? 0"
    :item="deliverTarget"
  />

  <DeliveryHistoryDialog v-model:visible="showHistoryDialog" :item="historyTarget" />
</template>

<style scoped lang="scss">
.detail-loading {
  display: flex;
  justify-content: center;
  padding: var(--space-6);
  color: var(--p-text-muted-color);
  font-size: var(--font-size-2xl);
}

.detail-layout {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  gap: var(--space-3);
}

.items-scroll-container {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.detail-header {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-2) var(--space-5);
  flex-shrink: 0;
}

.detail-meta {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.detail-meta-wide {
  grid-column: 1 / -1;
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

.detail-items-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.detail-items-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.section-title {
  font-weight: 600;
  font-size: var(--font-size-sm);
  color: var(--p-text-color);
}
</style>
