import { useI18n } from 'vue-i18n'

import { usePermissions } from '@/core/composables/usePermissions'
import { blockingPermission } from '@/core/utils/lifecycleActions'
import type { HasActions, LifecycleAction } from '@/core/utils/lifecycleActions'
import { permissionLabel } from '@/shared/utils/permissionLabels'

/**
 * The tooltip of a button the user lacks the rights for. A button whose
 * action needs a permission the user does not hold stays visible and
 * disabled, and says which permission it needs; `missing` answers that
 * sentence for the first permission missing, or '' when the user holds
 * them all. Wrap the disabled button in a span carrying the tooltip, since
 * a disabled button shows none of its own.
 */
export function useMissingPermission() {
  const { t } = useI18n()
  const { hasPermission } = usePermissions()

  function sentence(permission: string): string {
    return t('common.permissionMissing', { permission: permissionLabel(t, permission) })
  }

  function missing(...permissions: string[]): string {
    const lacking = permissions.find((permission) => !hasPermission(permission))
    return lacking ? sentence(lacking) : ''
  }

  /**
   * The tooltip of a lifecycle action the response's state allows: the
   * first of the action's base permissions the user lacks, else the extra
   * permission the backend reports the action blocked by, else ''.
   */
  function missingForAction(
    subject: HasActions | null | undefined,
    action: LifecycleAction,
    ...basePermissions: string[]
  ): string {
    const lacking = missing(...basePermissions)
    if (lacking) return lacking
    const extra = blockingPermission(subject, action)
    return extra ? sentence(extra) : ''
  }

  return { missing, missingForAction }
}
