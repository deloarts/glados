/**
 * Auto-Allocate, Manage Allocations and Fulfill from Stock all write
 * allocations, which the backend reserves for write:allocations. Without it
 * the buttons stay visible but disabled, and their wrapping span names the
 * missing permission.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { i18n } from '@/core/i18n'
import { Permission } from '@/core/auth/permissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeDemandItemResponse, userWithPermissions } from '@/test-utils/factories'

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: { items: [], total: 0, limit: 0, skip: 0 },
    }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    put: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import BoughtItemDemandDetailDialog from '../BoughtItemDemandDetailDialog.vue'

const ALLOCATION_LABELS = [
  'boughtItems.demands.detail.autoAllocate',
  'boughtItems.demands.detail.manageAllocations',
  'boughtItems.demands.detail.fulfillFromStock',
].map((key) => i18n.global.t(key))

async function mountDialog(permissions: string[]): Promise<VueWrapper> {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  const wrapper = mountWithApp(BoughtItemDemandDetailDialog, {
    pinia,
    attachTo: document.body,
    props: {
      visible: true,
      demand: makeDemandItemResponse({ id: 4, status: 'allocated', actions: ['allocate'] }),
    },
  })
  await flushPromises()
  return wrapper
}

function allocationButtons(wrapper: VueWrapper) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .filter((b) => ALLOCATION_LABELS.includes(b.props('label') as string))
}

describe('BoughtItemDemandDetailDialog allocation actions', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  it('disables them without write:allocations and names the permission', async () => {
    const wrapper = await mountDialog([Permission.WRITE_DEMAND_ITEMS])

    const buttons = allocationButtons(wrapper)
    expect(buttons).toHaveLength(3)
    for (const b of buttons) {
      expect(b.attributes('disabled')).toBeDefined()
      const span = b.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
      expect(span?.$_ptooltipValue).toBe('This needs the permission Write Allocations.')
    }

    wrapper.unmount()
  })

  it('enables Auto-Allocate and Manage with write:allocations', async () => {
    const wrapper = await mountDialog([Permission.WRITE_ALLOCATIONS])

    const [autoAllocate, manage] = allocationButtons(wrapper)
    expect(autoAllocate!.attributes('disabled')).toBeUndefined()
    expect(manage!.attributes('disabled')).toBeUndefined()

    wrapper.unmount()
  })
})
