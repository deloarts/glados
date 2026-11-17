/**
 * The detail dialog of a source item demand offers only the two statuses a
 * user sets, fulfilled and canceled, to holders of write:demand_items and
 * manage:demand_items while the demand is neither fulfilled nor canceled.
 * Both go through the status route, which applies that rule rather than the
 * lot permission of the separate cancel action, which needs write:lots and is
 * shown disabled, with the reason, to everyone else.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { i18n } from '@/core/i18n'
import { Permission } from '@/core/auth/permissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeSourceItemDemandResponse, userWithPermissions } from '@/test-utils/factories'

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: { items: [], total: 0, limit: 0, skip: 0 },
    }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    put: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import SourceItemDemandDetailDialog from '../SourceItemDemandDetailDialog.vue'
import { useSourceItemDemandsStore } from '@/features/source-items'
import type { SourceItemDemandResponse } from '@/features/source-items'

function makeDemand(overrides: Partial<SourceItemDemandResponse> = {}): SourceItemDemandResponse {
  // A live demand offers both manual actions; a fulfilled or canceled one
  // offers none (the demand intent table).
  const live = ['open', 'allocated', 'ordered'].includes(overrides.status ?? 'allocated')
  return makeSourceItemDemandResponse({
    actions: live ? ['cancel', 'fulfil', 'allocate', 'edit_quantity'] : [],
    status: 'allocated',
    ...overrides,
  })
}

const MANAGER = [Permission.WRITE_DEMAND_ITEMS, Permission.MANAGE_DEMAND_ITEMS]

function statusLabel(status: string): string {
  return i18n.global.t(`sourceItems.demands.status.${status}`)
}

async function mountDialog(demand: SourceItemDemandResponse, permissions: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  const store = useSourceItemDemandsStore()
  const canceled = { ...demand, status: 'canceled' as const }
  const updateStatus = vi.spyOn(store, 'updateStatus').mockResolvedValue(canceled)
  const cancel = vi.spyOn(store, 'cancel').mockResolvedValue(canceled)
  const cancelByStatus = vi.spyOn(store, 'cancelByStatus').mockResolvedValue(canceled)
  const wrapper = mountWithApp(SourceItemDemandDetailDialog, {
    pinia,
    attachTo: document.body,
    props: { visible: true, demand },
    global: { plugins: [ConfirmationService] },
  })
  await flushPromises()
  return { wrapper, updateStatus, cancel, cancelByStatus }
}

async function choose(testId: string): Promise<void> {
  const button = document.body.querySelector<HTMLButtonElement>(`[data-testid="${testId}"]`)
  expect(button).not.toBeNull()
  button!.click()
  await flushPromises()
}

function statusButtonLabels(wrapper: VueWrapper): string[] {
  const labels = ['open', 'allocated', 'ordered', 'fulfilled', 'canceled'].map(statusLabel)
  return wrapper
    .findAllComponents({ name: 'Button' })
    .map((b) => b.props('label') as string)
    .filter((label) => labels.includes(label))
}

// The dialog teleports to the body, so its buttons are found as components.
function cancelButton(wrapper: VueWrapper) {
  const label = i18n.global.t('sourceItems.demands.detail.cancelDemand')
  const button = wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === label)!
  return { element: button.element as HTMLButtonElement, trigger: () => button.trigger('click') }
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

describe('SourceItemDemandDetailDialog status actions', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  it('offers only fulfilled and canceled to a demand manager', async () => {
    const { wrapper } = await mountDialog(makeDemand(), MANAGER)

    expect(statusButtonLabels(wrapper)).toEqual([statusLabel('fulfilled'), statusLabel('canceled')])

    wrapper.unmount()
  })

  it('shows the offered status changes disabled without manage:demand_items and offers none on a fulfilled demand', async () => {
    const first = await mountDialog(makeDemand(), [Permission.WRITE_DEMAND_ITEMS])
    expectStatusButtonsBlocked(first.wrapper)
    first.wrapper.unmount()

    const second = await mountDialog(makeDemand({ status: 'fulfilled' }), MANAGER)
    expect(statusButtonLabels(second.wrapper)).toEqual([])
    second.wrapper.unmount()
  })

  it('cancels through the status route with the choice for the lot', async () => {
    const { wrapper, updateStatus, cancelByStatus } = await mountDialog(makeDemand(), MANAGER)

    await wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === statusLabel('canceled'))!
      .trigger('click')
    await flushPromises()
    expect(cancelByStatus).not.toHaveBeenCalled()

    await choose('cancel-prompt-demand-only')
    expect(cancelByStatus).toHaveBeenCalledWith(1, false)
    expect(updateStatus).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('marks fulfilled through the status route only once confirmed', async () => {
    const { wrapper, updateStatus } = await mountDialog(makeDemand(), MANAGER)

    await wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === statusLabel('fulfilled'))!
      .trigger('click')
    await flushPromises()
    const confirm = wrapper.findComponent({ name: 'ConfirmActionDialog' })
    expect(confirm.props('visible')).toBe(true)
    expect(updateStatus).not.toHaveBeenCalled()

    confirm.vm.$emit('confirm')
    await flushPromises()
    expect(updateStatus).toHaveBeenCalledWith(1, 'fulfilled')

    wrapper.unmount()
  })

  it('shows the cancel action of the lot disabled, with the reason, without write:lots', async () => {
    const manager = await mountDialog(makeDemand(), MANAGER)
    expect(cancelButton(manager.wrapper).element.disabled).toBe(true)
    manager.wrapper.unmount()

    const lotWriter = await mountDialog(makeDemand(), [Permission.WRITE_LOTS])
    expect(cancelButton(lotWriter.wrapper).element.disabled).toBe(false)
    lotWriter.wrapper.unmount()
  })

  it('disables the cancel action once the lot started, which the server no longer offers', async () => {
    const started = makeDemand({ actions: ['fulfil', 'allocate', 'edit_quantity'] })
    const { wrapper } = await mountDialog(started, [Permission.WRITE_LOTS, ...MANAGER])

    expect(cancelButton(wrapper).element.disabled).toBe(true)
    expect(statusButtonLabels(wrapper)).toEqual([statusLabel('fulfilled')])

    wrapper.unmount()
  })

  it('asks what becomes of the lot it names, then cancels the lot too', async () => {
    const { wrapper, cancel } = await mountDialog(makeDemand({ lot_number: 'LOT-0042' }), [
      Permission.WRITE_LOTS,
    ])

    await cancelButton(wrapper).trigger()
    await flushPromises()

    expect(document.body.textContent).toContain(
      i18n.global.t('sourceItems.demands.cancelPrompt.question', { lot: 'LOT-0042' }),
    )
    expect(cancel).not.toHaveBeenCalled()

    await choose('cancel-prompt-cancel-lot')
    expect(cancel).toHaveBeenCalledWith(1, true)

    wrapper.unmount()
  })

  it('cancels nothing when the prompt is left with Back', async () => {
    const { wrapper, cancel } = await mountDialog(makeDemand(), [Permission.WRITE_LOTS])

    await cancelButton(wrapper).trigger()
    await flushPromises()
    await choose('cancel-prompt-back')

    expect(cancel).not.toHaveBeenCalled()

    wrapper.unmount()
  })
})
