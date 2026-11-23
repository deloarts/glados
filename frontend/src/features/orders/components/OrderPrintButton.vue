<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { MenuItem } from 'openvue/menuitem'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { useOrderDocketDownload } from '../composables/useOrderDocketDownload'
import type { OrderResponse } from '../types/ordersResponse'

/**
 * The Print button of the order page. Its menu downloads the order docket or
 * sends it to its printer, the same two entries the row menu of the orders
 * list offers. Without the permission to print documents the button is
 * disabled and names it.
 */
const props = defineProps<{ order: OrderResponse }>()

const { t } = useI18n()
const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()
const { downloadingDocketId, downloadOrderDocket, printingDocketId, printOrderDocket } =
  useOrderDocketDownload()

const menu = ref<{ toggle(event: Event): void }>()
const canPrint = computed(() => hasPermission(Permission.PRINT_DOCUMENTS))
const busy = computed(
  () => downloadingDocketId.value === props.order.id || printingDocketId.value === props.order.id,
)

const items = computed<MenuItem[]>(() => [
  {
    key: 'download',
    label: t('orders.actions.downloadDocket'),
    icon: 'mdi mdi-file-document-outline',
    disabled: downloadingDocketId.value === props.order.id,
    command: () => void downloadOrderDocket(props.order),
  },
  {
    key: 'print',
    label: t('orders.actions.printDocket'),
    icon: 'mdi mdi-printer-outline',
    disabled: printingDocketId.value === props.order.id,
    command: () => void printOrderDocket(props.order),
  },
])

const menuPt = {
  itemLink: (options: { context: { item: MenuItem } }) => ({
    'data-testid': `order-docket-${String(options.context.item.key)}`,
  }),
}
</script>

<template>
  <span v-tooltip.bottom="missing(Permission.PRINT_DOCUMENTS) || undefined">
    <Button
      icon="mdi mdi-printer-outline"
      :label="t('orders.actions.print')"
      severity="contrast"
      text
      :disabled="!canPrint"
      :loading="busy"
      data-testid="order-print"
      @click="menu?.toggle($event)"
    />
  </span>
  <Menu ref="menu" :model="items" popup :pt="menuPt" />
</template>
