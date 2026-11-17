/**
 * The detail dialog of a bought item demand offers only the two statuses a
 * user sets, fulfilled and canceled; open, allocated and ordered follow from
 * the allocations. Both are irreversible, so the buttons appear only for
 * holders of write:demand_items and manage:demand_items and only while the
 * demand is neither fulfilled nor canceled. Canceling goes through the
 * cancel route, which releases the demand's allocations. Marking it fulfilled
 * asks first, since it releases what its order lines have not delivered yet.
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
import { useBoughtItemsDemandsStore } from '@/features/bought-items'
import type { BoughtItemDemandResponse } from '@/features/bought-items'

function makeDemand(overrides: Partial<BoughtItemDemandResponse> = {}): BoughtItemDemandResponse {
  // A live demand offers both manual actions; a fulfilled or canceled one
  // offers none (the demand intent table).
  const live = ['open', 'allocated', 'ordered'].includes(overrides.status ?? 'allocated')
  return makeDemandItemResponse({
    actions: live ? ['cancel', 'fulfil', 'allocate', 'edit_quantity'] : [],
    id: 4,
    status: 'allocated',
    ...overrides,
  })
}

const MANAGER = [Permission.WRITE_DEMAND_ITEMS, Permission.MANAGE_DEMAND_ITEMS]

function statusLabel(status: string): string {
  return i18n.global.t(`boughtItems.demands.status.${status}`)
}

async function mountDialog(demand: BoughtItemDemandResponse, permissions: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  const store = useBoughtItemsDemandsStore()
  const cancel = vi.spyOn(store, 'cancel').mockResolvedValue({ ...demand, status: 'canceled' })
  const updateStatus = vi
    .spyOn(store, 'updateStatus')
    .mockResolvedValue({ ...demand, status: 'fulfilled' })
  const wrapper = mountWithApp(BoughtItemDemandDetailDialog, {
    pinia,
    attachTo: document.body,
    props: { visible: true, demand },
  })
  await flushPromises()
  return { wrapper, cancel, updateStatus }
}

function statusButtonLabels(wrapper: VueWrapper): string[] {
  const labels = ['open', 'allocated', 'ordered', 'fulfilled', 'canceled'].map(statusLabel)
  return wrapper
    .findAllComponents({ name: 'Button' })
    .map((b) => b.props('label') as string)
    .filter((label) => labels.includes(label))
}

function button(wrapper: VueWrapper, status: string) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === statusLabel(status))!
}

function expectStatusButtonsBlocked(wrapper: VueWrapper): void {
  const buttons = wrapper
    .findAllComponents({ name: 'Button' })
    .filter((b) => [statusLabel('fulfilled'), statusLabel('canceled')].includes(b.props('label') as string))
  expect(buttons).toHaveLength(2)
  for (const b of buttons) {
    expect(b.attributes('disabled')).toBeDefined()
    const span = b.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
    expect(span?.$_ptooltipValue).toBe('This needs the permission Manage Demand Items.')
  }
}

describe('BoughtItemDemandDetailDialog status actions', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  it('offers only fulfilled and canceled to a demand manager', async () => {
    const { wrapper } = await mountDialog(makeDemand(), MANAGER)

    expect(statusButtonLabels(wrapper)).toEqual([statusLabel('fulfilled'), statusLabel('canceled')])

    wrapper.unmount()
  })

  it('shows the offered status changes disabled without manage:demand_items', async () => {
    const { wrapper } = await mountDialog(makeDemand(), [Permission.WRITE_DEMAND_ITEMS])

    expect(statusButtonLabels(wrapper)).toEqual([statusLabel('fulfilled'), statusLabel('canceled')])
    expectStatusButtonsBlocked(wrapper)

    wrapper.unmount()
  })

  it('offers no status change on a fulfilled demand', async () => {
    const { wrapper } = await mountDialog(makeDemand({ status: 'fulfilled' }), MANAGER)

    expect(statusButtonLabels(wrapper)).toEqual([])

    wrapper.unmount()
  })

  it('cancels through the cancel route and marks fulfilled through the status route', async () => {
    const { wrapper, cancel, updateStatus } = await mountDialog(makeDemand(), MANAGER)

    await button(wrapper, 'canceled').trigger('click')
    await flushPromises()
    expect(cancel).toHaveBeenCalledWith(4)
    expect(updateStatus).not.toHaveBeenCalled()

    await button(wrapper, 'fulfilled').trigger('click')
    await flushPromises()
    const confirm = wrapper.findComponent({ name: 'ConfirmActionDialog' })
    expect(confirm.props('visible')).toBe(true)
    expect(updateStatus).not.toHaveBeenCalled()

    confirm.vm.$emit('confirm')
    await flushPromises()
    expect(updateStatus).toHaveBeenCalledWith(4, 'fulfilled')

    wrapper.unmount()
  })
})
