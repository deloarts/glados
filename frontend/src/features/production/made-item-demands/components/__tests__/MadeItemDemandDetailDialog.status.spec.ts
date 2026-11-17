/**
 * The detail dialog of a made item demand offers only the two statuses a
 * user sets, fulfilled and canceled, to holders of write:demand_items and
 * manage:demand_items while the demand is neither fulfilled nor canceled.
 * Canceling opens the impact dialog, which cancels through the cancel route
 * on confirm, since a canceled demand takes its lots down with it.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { i18n } from '@/core/i18n'
import { Permission } from '@/core/auth/permissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeMadeItemDemandResponse, userWithPermissions } from '@/test-utils/factories'

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: { items: [], total: 0, limit: 0, skip: 0 },
    }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    put: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import MadeItemDemandDetailDialog from '../MadeItemDemandDetailDialog.vue'
import MadeItemDemandCancelDialog from '../MadeItemDemandCancelDialog.vue'
import { useMadeItemsDemandsStore } from '@/features/made-items'
import type { MadeItemDemandResponse } from '@/features/made-items'

function makeDemand(overrides: Partial<MadeItemDemandResponse> = {}): MadeItemDemandResponse {
  // A live demand offers both manual actions; a fulfilled or canceled one
  // offers none (the demand intent table).
  const live = ['open', 'allocated', 'ordered'].includes(overrides.status ?? 'ordered')
  return makeMadeItemDemandResponse({
    actions: live ? ['cancel', 'fulfil', 'allocate', 'edit_quantity'] : [],
    id: 6,
    status: 'ordered',
    ...overrides,
  })
}

const MANAGER = [Permission.WRITE_DEMAND_ITEMS, Permission.MANAGE_DEMAND_ITEMS]

function statusLabel(status: string): string {
  return i18n.global.t(`madeItems.demands.status.${status}`)
}

async function mountDialog(demand: MadeItemDemandResponse, permissions: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  const store = useMadeItemsDemandsStore()
  const cancel = vi.spyOn(store, 'cancel').mockResolvedValue({ ...demand, status: 'canceled' })
  const updateStatus = vi
    .spyOn(store, 'updateStatus')
    .mockResolvedValue({ ...demand, status: 'fulfilled' })
  const wrapper = mountWithApp(MadeItemDemandDetailDialog, {
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

describe('MadeItemDemandDetailDialog status actions', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  it('offers only fulfilled and canceled to a demand manager', async () => {
    const { wrapper } = await mountDialog(makeDemand(), MANAGER)

    expect(statusButtonLabels(wrapper)).toEqual([statusLabel('fulfilled'), statusLabel('canceled')])

    wrapper.unmount()
  })

  it('shows the offered status changes disabled without manage:demand_items and offers none on a canceled demand', async () => {
    const first = await mountDialog(makeDemand(), [Permission.WRITE_DEMAND_ITEMS])
    expectStatusButtonsBlocked(first.wrapper)
    first.wrapper.unmount()

    const second = await mountDialog(makeDemand({ status: 'canceled' }), MANAGER)
    expect(statusButtonLabels(second.wrapper)).toEqual([])
    second.wrapper.unmount()
  })

  it('opens the impact dialog to cancel and marks fulfilled through the status route', async () => {
    const { wrapper, cancel, updateStatus } = await mountDialog(makeDemand(), MANAGER)

    await button(wrapper, 'canceled').trigger('click')
    await flushPromises()
    expect(wrapper.findComponent(MadeItemDemandCancelDialog).props('visible')).toBe(true)
    expect(cancel).not.toHaveBeenCalled()

    await button(wrapper, 'fulfilled').trigger('click')
    await flushPromises()
    expect(updateStatus).toHaveBeenCalledWith(6, 'fulfilled')

    wrapper.unmount()
  })
})
