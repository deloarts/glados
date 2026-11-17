import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { Permission } from '@/core/auth/permissions'

import type { LotResponse } from '../../../types/productionLotsResponse'

// Same harness as the existing LotDetailContent.spec.ts, seeded with a
// pending (rather than not_required) lot so the Source card's Approve/Reject
// branch is what's on screen. Approve/Reject only render in the read-only
// record view (manageMode stays false throughout: see LotDetailContent.vue,
// the Source card's manage-only actions re-hosted for manage mode are
// change-source/create-demand, not approve/reject), so none of these tests
// need to toggle Manage on.
const { lotFixture } = vi.hoisted(() => {
  const lotFixture: LotResponse = {
    edit_version: 2,
    id: 1,
    created: '2026-07-01',
    changed: null,
    changed_by: null,
    changed_by_id: null,
    public_id: '00000000-0000-0000-0000-000000000001',
    lot_number: 'LOT-0001',
    quantity: 10,
    quantity_completed: 4,
    status: 'in_progress',
    priority: 'normal',
    note: null,
    required_delivery_date: null,
    creator_id: 1,
    creator: null,
    made_item_id: 1,
    made_item_part_number: 'PN-1',
    made_item_article_name: 'Bracket',
    made_item_revision: 'A',
    made_item_material: '1.0037',
    source_bought_item_id: null,
    source_item_id: 7,
    source_made_item_id: null,
    source_label: 'Stock',
    source_sublabel: '',
    demand_status: '',
    is_alteration: false,
    project_id: 42,
    project_number: 'P-001',
    project_customer: 'Acme',
    input_demand_id: null,
    source_approval_status: 'pending',
    positions: [],
    steps: [],
    actions: ['approve_source', 'reject_source', 'switch_source'],
    blocked_actions: {},
    canceled_at: null,
    completed_at: null,
    follow_up_lots: [],
    force_completed_at: null,
    held_at: null,
    origin_disposition: null,
    origin_lot_id: null,
    origin_lot_number: null,
    source_approved_by_id: null,
    source_approved_date: null,
    source_delivery_date: null,
    source_expected_delivery_date: null,
    source_order_id: null,
    source_order_number: null,
    source_rejected_by_id: null,
    source_rejected_date: null,
    source_rejection_reason: null,
  }
  return { lotFixture }
})

const getMock = vi.fn<(url: string) => Promise<unknown>>(async (url: string) => {
  if (/^\/production-lots\/\d+$/.test(url)) return { data: lotFixture }
  if (/^\/production-lots\/\d+\/events$/.test(url)) return { data: [] }
  if (/^\/production-lots\/\d+\/demands$/.test(url)) return { data: [] }
  if (/^\/production-lots\/\d+\/material-receipts$/.test(url)) return { data: [] }
  return { data: { items: [], total: 0, limit: 1000, skip: 0 } }
})
const postMock = vi
  .fn<(url: string, payload?: unknown) => Promise<unknown>>()
  .mockResolvedValue({ data: {} })

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
    post: (url: string, payload?: unknown) => postMock(url, payload),
    put: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: [] }),
    delete: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

// Same technique as UserFormDialog.spec.ts. It lets the toast content be
// asserted directly instead of driving a real <Toast>'s DOM/timing.
const toastAddMock = vi.fn<(options: unknown) => void>()
vi.mock('openvue/usetoast', () => ({
  useToast: () => ({ add: toastAddMock }),
}))

import LotDetailContent from '../LotDetailContent.vue'
import LotRejectSourceDialog from '../LotRejectSourceDialog.vue'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { userWithPermissions } from '@/test-utils/factories'

function mountDialog(permissions: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)

  return mountWithApp(LotDetailContent, {
    pinia,
    attachTo: document.body,
    props: { lotId: 1 },
    global: {
      plugins: [ConfirmationService],
      stubs: { RouterLink: true },
    },
  })
}

const t = (key: string): string => i18n.global.t(key) as string

// The Source card sits behind the record's Source & Demand tab, which only
// mounts once it is opened (Execution shows first).
async function openSourceTab(wrapper: ReturnType<typeof mountDialog>): Promise<void> {
  const tab = wrapper
    .findAll('[role="tab"]')
    .find((el) => el.text().includes(t('production.lots.detail.record.tabs.sourceAndDemand')))
  expect(tab).toBeTruthy()
  await tab!.trigger('click')
  await flushPromises()
}

describe('LotDetailContent source approval', () => {
  it('Approve calls approveLotSource, refetches the lot, and shows a success toast', async () => {
    const wrapper = mountDialog([Permission.WRITE_LOTS, Permission.MANAGE_LOTS])
    await flushPromises()
    await flushPromises()

    await openSourceTab(wrapper)
    getMock.mockClear()
    postMock.mockClear()
    toastAddMock.mockClear()

    const approveButton = wrapper
      .findComponent({ name: 'LotRecordSourceDemand' })
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === t('production.lots.detail.record.sourceApproval.approve'))
    expect(approveButton).toBeDefined()

    await approveButton!.trigger('click')
    await flushPromises()

    expect(postMock).toHaveBeenCalledWith('/production-lots/1/source/approve', {
      expected_edit_version: 2,
    })
    // detailStore.refetch() re-fetches the same lot endpoint.
    expect(getMock).toHaveBeenCalledWith('/production-lots/1')
    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({
        severity: 'success',
        detail: t('production.lots.detail.record.sourceApproval.approveSuccess'),
      }),
    )

    wrapper.unmount()
  })

  it('a double click on Approve sends the approval once', async () => {
    const wrapper = mountDialog([Permission.WRITE_LOTS, Permission.MANAGE_LOTS])
    await flushPromises()
    await flushPromises()
    await openSourceTab(wrapper)
    postMock.mockClear()
    // Held open, so the second click lands while the first is on its way.
    postMock.mockImplementationOnce(() => new Promise(() => {}))

    const approve = wrapper
      .findComponent({ name: 'LotRecordSourceDemand' })
      .get('[data-testid="source-approve"]')
    ;(approve.element as HTMLButtonElement).click()
    await flushPromises()
    ;(approve.element as HTMLButtonElement).click()
    await flushPromises()

    expect(postMock.mock.calls.filter(([url]) => url.endsWith('/source/approve'))).toHaveLength(1)

    wrapper.unmount()
  })

  it('Reject dialog confirm calls rejectLotSource with the trimmed reason', async () => {
    const wrapper = mountDialog([Permission.WRITE_LOTS, Permission.MANAGE_LOTS])
    await flushPromises()
    await flushPromises()

    await openSourceTab(wrapper)
    postMock.mockClear()
    toastAddMock.mockClear()

    const rejectTriggerButton = wrapper
      .findComponent({ name: 'LotRecordSourceDemand' })
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === t('production.lots.detail.record.sourceApproval.reject'))
    expect(rejectTriggerButton).toBeDefined()

    await rejectTriggerButton!.trigger('click')
    await flushPromises()
    await flushPromises()

    const dialog = wrapper.findComponent(LotRejectSourceDialog)
    expect(dialog.props('visible')).toBe(true)

    await dialog.findComponent({ name: 'Textarea' }).setValue('Wrong material dimension')
    const confirmButton = dialog
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === t('production.lots.detail.record.sourceApproval.reject'))
    expect(confirmButton).toBeDefined()

    await confirmButton!.trigger('click')
    await flushPromises()

    expect(postMock).toHaveBeenCalledWith('/production-lots/1/source/reject', {
      reason: 'Wrong material dimension',
      expected_edit_version: 2,
    })
    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({
        severity: 'success',
        detail: t('production.lots.detail.record.sourceApproval.rejectSuccess'),
      }),
    )

    wrapper.unmount()
  })

  it('without manage:lots the offered decisions stay visible but disabled', async () => {
    const wrapper = mountDialog([Permission.WRITE_LOTS])
    await flushPromises()
    await flushPromises()
    await openSourceTab(wrapper)

    const section = wrapper.findComponent({ name: 'LotRecordSourceDemand' })
    expect(section.get('[data-testid="source-approve"]').attributes('disabled')).toBeDefined()
    expect(section.get('[data-testid="source-reject"]').attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  it('a lot the server offers no decision on shows no Approve or Reject', async () => {
    const actions = lotFixture.actions
    lotFixture.actions = ['switch_source']
    try {
      const wrapper = mountDialog([Permission.WRITE_LOTS, Permission.MANAGE_LOTS])
      await flushPromises()
      await flushPromises()
      await openSourceTab(wrapper)

      const section = wrapper.findComponent({ name: 'LotRecordSourceDemand' })
      expect(section.find('[data-testid="source-approve"]').exists()).toBe(false)
      expect(section.find('[data-testid="source-reject"]').exists()).toBe(false)

      wrapper.unmount()
    } finally {
      lotFixture.actions = actions
    }
  })
})
