<script setup lang="ts">
// Actions cell of an order item row. While the row is edited it holds the
// save and cancel buttons; otherwise the page variant shows the most used
// actions inline, and both variants offer the overflow menu.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { offersAction } from '@/core/utils/lifecycleActions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { orderItemActionGates as gates } from '../composables/useOrderItemActions'

import type { OrderItemPermissions } from '../composables/useOrderItemActions'
import type { OrderItemResponse } from '../types/ordersResponse'

const props = defineProps<{
  item: OrderItemResponse
  permissions: OrderItemPermissions
  isPage: boolean
  editing: boolean
  saving: boolean
  markingOrdered: boolean
  busy: boolean
}>()

const emit = defineEmits<{
  save: []
  cancel: []
  deliver: []
  markOrdered: []
  edit: []
  overflow: [event: Event]
}>()

const { t } = useI18n()
const { missing, missingForAction } = useMissingPermission()

// The gates with every permission held say whether the line's state offers
// an action; the inline buttons then show and are disabled, naming the
// missing permission, when the user's own permissions do not allow it.
const ALL_PERMISSIONS: OrderItemPermissions = {
  canWrite: true,
  canManage: true,
  canReceiveDeliveries: true,
}

const deliverBlocked = computed(() =>
  props.permissions.canReceiveDeliveries ? '' : missing(Permission.RECEIVE_DELIVERIES),
)
const writeBlocked = computed(() =>
  props.permissions.canWrite ? '' : missing(Permission.WRITE_ORDERS),
)
// A line the supplier already holds is marked only with manage:orders, which
// the line's blocked actions name.
const markOrderedBlocked = computed(
  () => writeBlocked.value || missingForAction(props.item, 'mark_ordered'),
)
// A submitted line is edited only with manage:orders, which the line's
// blocked actions name.
const editBlocked = computed(
  () => writeBlocked.value || missingForAction(props.item, 'edit'),
)
</script>

<template>
  <div class="item-actions">
    <template v-if="editing">
      <Button
        icon="mdi mdi-check"
        size="small"
        severity="success"
        text
        rounded
        :loading="saving"
        v-tooltip.focus="t('common.save')"
        :aria-label="t('common.save')"
        @click="emit('save')"
      />
      <Button
        icon="mdi mdi-close"
        size="small"
        severity="secondary"
        text
        rounded
        :disabled="saving"
        v-tooltip.focus="t('common.cancel')"
        :aria-label="t('common.cancel')"
        @click="emit('cancel')"
      />
    </template>
    <template v-else>
      <template v-if="isPage">
        <span
          v-if="gates.deliver(item, ALL_PERMISSIONS)"
          v-tooltip.top="deliverBlocked || undefined"
        >
          <Button
            icon="mdi mdi-package-variant-closed-check"
            size="small"
            severity="success"
            text
            rounded
            :disabled="!gates.deliver(item, permissions)"
            v-tooltip.focus="t('orders.actions.deliver')"
            :aria-label="t('orders.actions.deliver')"
            @click="emit('deliver')"
          />
        </span>
        <span
          v-if="offersAction(item, 'mark_ordered')"
          v-tooltip.top="markOrderedBlocked || undefined"
        >
          <Button
            icon="mdi mdi-cart-check"
            size="small"
            severity="info"
            text
            rounded
            :disabled="!gates.markOrdered(item, permissions)"
            :loading="markingOrdered"
            v-tooltip.focus="t('orders.actions.markOrdered')"
            :aria-label="t('orders.actions.markOrdered')"
            @click="emit('markOrdered')"
          />
        </span>
        <span v-if="offersAction(item, 'edit')" v-tooltip.top="editBlocked || undefined">
          <Button
            icon="mdi mdi-pencil"
            size="small"
            severity="secondary"
            text
            rounded
            :disabled="!gates.edit(item, permissions)"
            v-tooltip.focus="t('orders.actions.editItem')"
            :aria-label="t('orders.actions.editItem')"
            @click="emit('edit')"
          />
        </span>
      </template>

      <Button
        icon="mdi mdi-dots-vertical"
        size="small"
        severity="secondary"
        text
        rounded
        :loading="busy"
        :aria-label="t('orders.actions.moreActions')"
        @click="emit('overflow', $event)"
      />
    </template>
  </div>
</template>

<style scoped lang="scss">
.item-actions {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}
</style>
