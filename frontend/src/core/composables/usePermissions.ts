import { useCurrentUserStore } from '@/core/stores/currentUserStore'

export function usePermissions() {
  const store = useCurrentUserStore()

  function hasPermission(permission: string): boolean {
    if (!store.user) return false
    if (store.user.is_systemuser) return true
    return store.user.permissions.includes(permission)
  }

  return { hasPermission }
}
