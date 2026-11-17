<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import {
  anyHasAction,
  anyOffersAction,
  blockingPermission,
  hasAction,
  offersAction,
} from '@/core/utils/lifecycleActions'
import type { LifecycleAction } from '@/core/utils/lifecycleActions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { hasDeliverableLines } from '../../composables/useOrderItemActions'

import type { OrderResponse } from '../../types/ordersResponse'

const props = defineProps<{
  order: OrderResponse
  canWrite: boolean
  canManage: boolean
  canReceiveDeliveries: boolean
  markingAllRequestedPending: boolean
  markingAllOrderedPending: boolean
}>()

const emit = defineEmits<{
  cancel: [order: OrderResponse]
  'mark-all-requested': [order: OrderResponse]
  'mark-all-ordered': [order: OrderResponse]
  'deliver-all': [order: OrderResponse]
  edit: [order: OrderResponse, event: Event]
  'add-item': [order: OrderResponse]
}>()

const { t } = useI18n()
const { missing, missingForAction } = useMissingPermission()

// The order's state decides which buttons show; a missing permission leaves
// them visible but disabled, with the permission named in the tooltip.
const writeBlocked = computed(() => (props.canWrite ? '' : missing(Permission.WRITE_ORDERS)))
const deliverBlocked = computed(() =>
  props.canReceiveDeliveries ? '' : missing(Permission.RECEIVE_DELIVERIES),
)
// Past REQUESTED a cancel also needs manage:orders, which the order's
// blocked actions name.
const cancelBlocked = computed(() => writeBlocked.value || missingForAction(props.order, 'cancel'))

// A mark-all is offered while a line's state allows the mark. When no line
// allows it to this user, the lines name the permission it lacks, which
// past REQUESTED is manage:orders.
function markAllBlocked(action: LifecycleAction): string {
  if (writeBlocked.value) return writeBlocked.value
  const items = props.order.items ?? []
  if (anyHasAction(items, action)) return ''
  const blocked = items.find((item) => blockingPermission(item, action) !== null)
  return blocked ? missingForAction(blocked, action) : ''
}
</script>

<template>
  <div class="row-actions">
    <span v-if="offersAction(order, 'cancel')" v-tooltip.top="cancelBlocked || undefined">
      <Button
        icon="mdi mdi-close-circle-outline"
        size="small"
        severity="danger"
        text
        rounded
        :disabled="!canWrite || !hasAction(order, 'cancel')"
        v-tooltip.focus="t('orders.actions.cancel')"
        :aria-label="t('orders.actions.cancel')"
        @click="emit('cancel', order)"
      />
    </span>
    <span
      v-if="anyOffersAction(order.items ?? [], 'mark_requested')"
      v-tooltip.top="markAllBlocked('mark_requested') || undefined"
    >
      <Button
        icon="mdi mdi-message-question-outline"
        size="small"
        severity="help"
        text
        rounded
        :disabled="!canWrite || !anyHasAction(order.items ?? [], 'mark_requested')"
        :loading="markingAllRequestedPending"
        data-testid="mark-all-requested"
        v-tooltip="t('orders.actions.markAllRequested')"
        :aria-label="t('orders.actions.markAllRequested')"
        @click="emit('mark-all-requested', order)"
      />
    </span>
    <span
      v-if="anyOffersAction(order.items ?? [], 'mark_ordered')"
      v-tooltip.top="markAllBlocked('mark_ordered') || undefined"
    >
      <Button
        icon="mdi mdi-cart-check"
        size="small"
        severity="info"
        text
        rounded
        :disabled="!canWrite || !anyHasAction(order.items ?? [], 'mark_ordered')"
        :loading="markingAllOrderedPending"
        data-testid="mark-all-ordered"
        v-tooltip="t('orders.actions.markAllOrdered')"
        :aria-label="t('orders.actions.markAllOrdered')"
        @click="emit('mark-all-ordered', order)"
      />
    </span>
    <span v-if="hasDeliverableLines(order)" v-tooltip.top="deliverBlocked || undefined">
      <Button
        icon="mdi mdi-package-variant-closed-check"
        size="small"
        severity="success"
        text
        rounded
        :disabled="!canReceiveDeliveries"
        data-testid="deliver-all"
        v-tooltip="t('orders.actions.deliverAll')"
        :aria-label="t('orders.actions.deliverAll')"
        @click="emit('deliver-all', order)"
      />
    </span>
    <span v-tooltip.top="writeBlocked || undefined">
      <Button
        icon="mdi mdi-pencil"
        size="small"
        severity="secondary"
        text
        rounded
        :disabled="!canWrite"
        v-tooltip.focus="t('orders.actions.edit')"
        :aria-label="t('orders.actions.edit')"
        @click="emit('edit', order, $event)"
      />
    </span>
    <span v-tooltip.top="writeBlocked || undefined">
      <Button
        icon="mdi mdi-plus"
        size="small"
        severity="secondary"
        text
        rounded
        :disabled="!canWrite"
        v-tooltip.focus="t('orders.actions.addItem')"
        :aria-label="t('orders.actions.addItem')"
        @click="emit('add-item', order)"
      />
    </span>
  </div>
</template>
