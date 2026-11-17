import { computed } from 'vue'

import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { Permission } from '@/core/auth/permissions'

/**
 * Permissions the current user may grant to a new API key or PAT: capped at
 * their own permission set (system users may grant anything), minus the
 * settings/key-management permissions a token can never hold. Mirrors
 * ApiKeyRules/PatRules.assert_permissions_allowed on the backend, this is
 * a UX filter only, the backend is the actual authority.
 */
export function useGrantablePermissions() {
  const userStore = useCurrentUserStore()

  const grantablePermissions = computed<string[]>(() => {
    const neverGrantable: readonly string[] = Permission.NEVER_GRANTABLE_TO_TOKENS
    const own = userStore.user?.is_systemuser ? Permission.ALL : (userStore.user?.permissions ?? [])
    return own.filter((perm) => !neverGrantable.includes(perm))
  })

  return { grantablePermissions }
}
