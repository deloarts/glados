import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { MenuItem } from 'openvue/menuitem'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { offersAction } from '@/core/utils/lifecycleActions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import type { OrderEditField } from '../components/OrderFieldEditDialog.vue'
import type { OrderResponse } from '../types/ordersResponse'
import { orderActionGates } from './useOrderItemActions'

/** Structural, since only open() is called. */
interface OrderFieldEditDialogApi {
  open(order: OrderResponse, field: OrderEditField): void
}

/**
 * The per-field edit menu behind OrderFieldEditDialog. Every item carries an
 * icon, since the detail page shows them as toolbar buttons where the icon
 * marks them as edit actions. Each item is disabled on its own, with the
 * reason as its title: the header fields follow the order's edit action, the
 * supplier order numbers their own, which a user with only write:orders keeps
 * after the order went out.
 */
export function useOrderEditFields() {
  const { t } = useI18n()
  const { hasPermission } = usePermissions()
  const { missingForAction } = useMissingPermission()
  const canWrite = computed(() => hasPermission(Permission.WRITE_ORDERS))

  const dialogRef = ref<OrderFieldEditDialogApi>()

  function open(order: OrderResponse, field: OrderEditField): void {
    dialogRef.value?.open(order, field)
  }

  function headerBlocked(order: OrderResponse): string | undefined {
    if (!offersAction(order, 'edit')) return undefined
    return missingForAction(order, 'edit', Permission.WRITE_ORDERS) || undefined
  }

  function numbersBlocked(order: OrderResponse): string | undefined {
    if (!offersAction(order, 'edit_supplier_order_numbers')) {
      return t('orders.edit.supplierOrderNumbersLocked')
    }
    return missingForAction(order, 'edit_supplier_order_numbers', Permission.WRITE_ORDERS) || undefined
  }

  function menuItems(order: OrderResponse): MenuItem[] {
    const header = {
      disabled: !orderActionGates.edit(order, canWrite.value),
      title: headerBlocked(order),
    }
    const numbers = {
      disabled: !orderActionGates.editSupplierOrderNumbers(order, canWrite.value),
      title: numbersBlocked(order),
    }
    return [
      {
        label: t('orders.edit.fields.supplier'),
        icon: 'mdi mdi-domain',
        ...header,
        command: () => open(order, 'supplier'),
      },
      {
        label: t('orders.edit.fields.expectedDelivery'),
        icon: 'mdi mdi-calendar-clock-outline',
        ...header,
        command: () => open(order, 'expected_delivery_date'),
      },
      {
        label: t('orders.edit.fields.storagePlace'),
        icon: 'mdi mdi-map-marker-outline',
        ...header,
        command: () => open(order, 'storage_place'),
      },
      {
        label: t('orders.edit.fields.supplierOrderNumbers'),
        icon: 'mdi mdi-pound-box-outline',
        ...numbers,
        command: () => open(order, 'supplier_order_numbers'),
      },
      {
        label: t('orders.edit.fields.note'),
        icon: 'mdi mdi-note-text-outline',
        ...header,
        command: () => open(order, 'note'),
      },
    ]
  }

  return { dialogRef, open, menuItems }
}
