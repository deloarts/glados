<script setup lang="ts">
/**
 * Offered after an order mail goes out, to mark the items requested or
 * ordered. Owns the marking so every sending surface gets the follow-up;
 * marked fires afterwards for consumers that need to refresh.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { HelpDrawer } from '@/shared/help'
import { useOrdersStore } from '../stores/ordersStore'
import type { OrderMailType } from '../composables/useOrderMailComposer'
import type { OrderResponse } from '../types/ordersResponse'

const props = defineProps<{
  order: OrderResponse | null
  mailType: OrderMailType
}>()

const visible = defineModel<boolean>('visible', { default: false })
const emit = defineEmits<{ marked: [] }>()

const { t } = useI18n()
const ordersStore = useOrdersStore()

const markingRequested = ref(false)
const markingOrdered = ref(false)
const explainVisible = ref(false)

async function markAllRequested(): Promise<void> {
  if (!props.order) return
  markingRequested.value = true
  try {
    await ordersStore.markAllItemsRequested(props.order.id)
    visible.value = false
    emit('marked')
  } finally {
    markingRequested.value = false
  }
}

async function markAllOrdered(): Promise<void> {
  if (!props.order) return
  markingOrdered.value = true
  try {
    await ordersStore.markAllItemsOrdered(props.order.id)
    visible.value = false
    emit('marked')
  } finally {
    markingOrdered.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <template #header>
      <div class="post-send-header">
        <span class="p-dialog-title">{{ t('orders.mail.postSendTitle') }}</span>
        <Button
          type="button"
          class="post-send-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('orders.explain.postSend')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('orders.explain.postSend')"
          @click="explainVisible = true"
        />
      </div>
    </template>
    <p style="margin: 0">{{ t('orders.mail.postSendMessage') }}</p>
    <template #footer>
      <Button
        :label="t('orders.mail.postSendSkip')"
        severity="secondary"
        @click="visible = false"
      />
      <Button
        :label="t('orders.actions.markAllRequested')"
        icon="mdi mdi-message-question-outline"
        :severity="mailType === 'request' ? 'help' : 'secondary'"
        :loading="markingRequested"
        @click="markAllRequested"
      />
      <Button
        :label="t('orders.actions.markAllOrdered')"
        icon="mdi mdi-cart-check"
        :severity="mailType === 'order' ? 'info' : 'secondary'"
        :loading="markingOrdered"
        @click="markAllOrdered"
      />
    </template>
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="procurement/order-documents" anchor="post-send" />
</template>

<style scoped lang="scss">
.post-send-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.post-send-explain-button :deep(.mdi) {
  font-size: var(--font-size-sm);
}
</style>
