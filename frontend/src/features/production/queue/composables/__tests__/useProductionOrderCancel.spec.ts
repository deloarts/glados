import { describe, it, expect, vi, beforeEach } from 'vitest'
import { defineComponent } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

import { Permission } from '@/core/auth/permissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeProductionOrderResponse, userWithPermissions } from '@/test-utils/factories'

const askMock = vi.hoisted(() => vi.fn<(options: Record<string, unknown>) => Promise<boolean>>())

vi.mock('@/shared/composables/useConfirmAsync', () => ({
  useConfirmAsync: () => ({ ask: askMock }),
}))

import { useProductionOrderCancel } from '../useProductionOrderCancel'

function setup(permissions: string[] = []) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  let api!: ReturnType<typeof useProductionOrderCancel>
  mountWithApp(
    defineComponent({
      setup() {
        api = useProductionOrderCancel()
        return () => null
      },
    }),
    { pinia },
  )
  return api
}

describe('useProductionOrderCancel', () => {
  beforeEach(() => {
    askMock.mockReset()
  })

  it('lets the creator cancel their own order', () => {
    const { cancelBlocked } = setup()
    expect(cancelBlocked(makeProductionOrderResponse({ creator_id: 1 }))).toBe('')
  })

  it("names Manage Production Orders on another user's order", () => {
    const { cancelBlocked } = setup()
    expect(cancelBlocked(makeProductionOrderResponse({ creator_id: 99 }))).toBe(
      'Another user created this order, so canceling it needs the permission Manage Production Orders.',
    )
  })

  it("lets Manage Production Orders cancel another user's order", () => {
    const { cancelBlocked } = setup([Permission.MANAGE_PRODUCTION_ORDERS])
    expect(cancelBlocked(makeProductionOrderResponse({ creator_id: 99 }))).toBe('')
  })

  it('asks before the cancel and names the order', async () => {
    askMock.mockResolvedValue(false)
    const { confirmCancel } = setup()

    const go = await confirmCancel(
      makeProductionOrderResponse({ production_order_number: 'PO-7' }),
    )

    expect(go).toBe(false)
    expect(askMock).toHaveBeenCalledOnce()
    expect(askMock.mock.calls[0]![0].message).toBe(
      'Cancel PO-7? The order stops and takes no further work. This cannot be undone.',
    )
  })
})
