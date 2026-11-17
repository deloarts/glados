import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { Permission } from '@/core/auth/permissions'
import { makeUserResponse } from '@/test-utils/factories'
import { usePermissions } from '../usePermissions'

describe('usePermissions', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('lacks every permission when nobody is signed in', () => {
    const { hasPermission } = usePermissions()

    expect(hasPermission(Permission.WRITE_LOTS)).toBe(false)
  })

  it('grants every permission to a system user, regardless of their stored permission list', () => {
    useCurrentUserStore().user = makeUserResponse({ is_systemuser: true, permissions: [] })
    const { hasPermission } = usePermissions()

    expect(hasPermission(Permission.WRITE_SETTINGS)).toBe(true)
    expect(hasPermission('some:unknown_permission')).toBe(true)
  })

  it("grants a permission present in a regular user's permission list", () => {
    useCurrentUserStore().user = makeUserResponse({ permissions: [Permission.WRITE_LOTS] })
    const { hasPermission } = usePermissions()

    expect(hasPermission(Permission.WRITE_LOTS)).toBe(true)
  })

  it("denies a permission absent from a regular user's permission list", () => {
    useCurrentUserStore().user = makeUserResponse({ permissions: [Permission.WRITE_LOTS] })
    const { hasPermission } = usePermissions()

    expect(hasPermission(Permission.MANAGE_LOTS)).toBe(false)
  })

  it('reacts to the signed-in user being cleared, e.g. sign-out', () => {
    const store = useCurrentUserStore()
    store.user = makeUserResponse({ permissions: [Permission.WRITE_LOTS] })
    const { hasPermission } = usePermissions()
    expect(hasPermission(Permission.WRITE_LOTS)).toBe(true)

    store.user = null

    expect(hasPermission(Permission.WRITE_LOTS)).toBe(false)
  })

  it('reacts to a different user signing in with a different permission set', () => {
    const store = useCurrentUserStore()
    store.user = makeUserResponse({ permissions: [Permission.WRITE_LOTS] })
    const { hasPermission } = usePermissions()
    expect(hasPermission(Permission.WRITE_LOTS)).toBe(true)

    store.user = makeUserResponse({ permissions: [Permission.MANAGE_LOTS] })

    expect(hasPermission(Permission.WRITE_LOTS)).toBe(false)
    expect(hasPermission(Permission.MANAGE_LOTS)).toBe(true)
  })
})
