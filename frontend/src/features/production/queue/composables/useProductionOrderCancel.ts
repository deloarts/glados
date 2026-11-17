import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useConfirmAsync } from '@/shared/composables/useConfirmAsync'
import { permissionLabel } from '@/shared/utils/permissionLabels'

import type { ProductionOrderResponse } from '../../types/productionOrdersResponse'

/**
 * The Cancel action of a production order on the queue card and the
 * machine page. The backend lets the order's creator cancel it and anyone
 * else only with Manage Production Orders, so `cancelBlocked` mirrors that
 * rule as the tooltip of the disabled control, or '' when the user may
 * cancel. `confirmCancel` asks before the cancel, which cannot be undone.
 */
export function useProductionOrderCancel() {
  const { t } = useI18n()
  const { hasPermission } = usePermissions()
  const currentUserStore = useCurrentUserStore()
  const { ask } = useConfirmAsync()

  function cancelBlocked(order: ProductionOrderResponse): string {
    if (hasPermission(Permission.MANAGE_PRODUCTION_ORDERS)) return ''
    if (order.creator_id === currentUserStore.user?.id) return ''
    return t('productionQueue.card.cancelOthersTooltip', {
      permission: permissionLabel(t, Permission.MANAGE_PRODUCTION_ORDERS),
    })
  }

  function confirmCancel(order: ProductionOrderResponse): Promise<boolean> {
    return ask({
      header: t('productionQueue.card.cancelConfirm.header'),
      message: t('productionQueue.card.cancelConfirm.message', {
        number: order.production_order_number,
      }),
      icon: 'mdi mdi-alert',
      rejectProps: { label: t('common.cancel'), severity: 'secondary' },
      acceptProps: { label: t('productionQueue.card.cancelConfirm.accept'), severity: 'danger' },
    })
  }

  return { cancelBlocked, confirmCancel }
}
