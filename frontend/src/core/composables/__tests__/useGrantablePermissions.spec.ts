import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { Permission } from '@/core/auth/permissions'
import { makeUserResponse } from '@/test-utils/factories'
import { useGrantablePermissions } from '../useGrantablePermissions'

describe('useGrantablePermissions', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('is empty when nobody is signed in', () => {
    const { grantablePermissions } = useGrantablePermissions()

    expect(grantablePermissions.value).toEqual([])
  })

  it('grants every permission except the tokens-only exclusions for a system user', () => {
    useCurrentUserStore().user = makeUserResponse({ is_systemuser: true, permissions: [] })
    const { grantablePermissions } = useGrantablePermissions()

    // Widened to `readonly string[]`, mirroring useGrantablePermissions.ts
    // itself: NEVER_GRANTABLE_TO_TOKENS's own literal-union type is narrower
    // than the permission strings in Permission.ALL, so `.includes()` would
    // otherwise reject every permission outside its own three-member union.
    const neverGrantable: readonly string[] = Permission.NEVER_GRANTABLE_TO_TOKENS
    const expected = Permission.ALL.filter((permission) => !neverGrantable.includes(permission))
    expect(grantablePermissions.value).toEqual(expected)
  })

  it("caps a regular user to their own permissions, minus the never-grantable ones", () => {
    useCurrentUserStore().user = makeUserResponse({
      is_systemuser: false,
      permissions: [
        Permission.WRITE_LOTS,
        Permission.MANAGE_LOTS,
        Permission.WRITE_SETTINGS,
        Permission.READ_SETTINGS,
        Permission.MANAGE_API_KEYS,
      ],
    })

    const { grantablePermissions } = useGrantablePermissions()

    expect(grantablePermissions.value).toEqual([Permission.WRITE_LOTS, Permission.MANAGE_LOTS])
  })

  it('recomputes when the signed-in user changes', () => {
    const store = useCurrentUserStore()
    const { grantablePermissions } = useGrantablePermissions()
    expect(grantablePermissions.value).toEqual([])

    store.user = makeUserResponse({ permissions: [Permission.WRITE_LOTS] })

    expect(grantablePermissions.value).toEqual([Permission.WRITE_LOTS])
  })
})
