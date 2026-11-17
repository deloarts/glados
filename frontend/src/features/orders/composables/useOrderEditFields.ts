import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { MenuItem } from 'openvue/menuitem'

import type { OrderEditField } from '../components/OrderFieldEditDialog.vue'
import type { OrderResponse } from '../types/ordersResponse'

/** Structural, since only open() is called. */
interface OrderFieldEditDialogApi {
  open(order: OrderResponse, field: OrderEditField): void
}

/**
 * The per-field edit menu behind OrderFieldEditDialog. Every item carries an
 * icon, since the detail page shows them as toolbar buttons where the icon
 * marks them as edit actions.
 */
export function useOrderEditFields() {
  const { t } = useI18n()

  const dialogRef = ref<OrderFieldEditDialogApi>()

  function open(order: OrderResponse, field: OrderEditField): void {
    dialogRef.value?.open(order, field)
  }

  function menuItems(order: OrderResponse): MenuItem[] {
    return [
      {
        label: t('orders.edit.fields.supplier'),
        icon: 'mdi mdi-domain',
        command: () => open(order, 'supplier'),
      },
      {
        label: t('orders.edit.fields.expectedDelivery'),
        icon: 'mdi mdi-calendar-clock-outline',
        command: () => open(order, 'expected_delivery_date'),
      },
      {
        label: t('orders.edit.fields.storagePlace'),
        icon: 'mdi mdi-map-marker-outline',
        command: () => open(order, 'storage_place'),
      },
      {
        label: t('orders.edit.fields.note'),
        icon: 'mdi mdi-note-text-outline',
        command: () => open(order, 'note'),
      },
    ]
  }

  return { dialogRef, open, menuItems }
}
