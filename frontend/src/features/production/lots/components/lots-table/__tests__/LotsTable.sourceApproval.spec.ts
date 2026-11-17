import { describe, it, expect, vi } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { useProductionLotsStore } from '../../../../stores/productionLotsStore'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { makeLotSummaryResponse, makeTestRouter, userWithPermissions } from '@/test-utils/factories'

import type { LotSummaryResponse } from '../../../../types/productionLotsResponse'

// Same technique OrdersTable.spec.ts/LotsTable.spec.ts use: the nested
// OrderDetailDialog calls useConfirm() in its own setup, mocked rather than
// registering a real ConfirmationService since nothing here exercises it.
vi.mock('openvue/useconfirm', () => ({
  useConfirm: () => ({ require: vi.fn<(options: unknown) => void>() }),
}))

const postMock = vi.fn<(url: string, payload?: unknown) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: vi
      .fn<() => Promise<unknown>>()
      .mockResolvedValue({ data: { items: [], total: 0, limit: 1000, skip: 0 } }),
    post: (url: string, payload?: unknown) => postMock(url, payload),
  },
}))

import LotsTable from '../LotsTable.vue'
import type { LifecycleAction } from '@/core/utils/lifecycleActions'

const t = (key: string): string => i18n.global.t(key) as string

function makeLot(overrides: Partial<LotSummaryResponse> = {}): LotSummaryResponse {
  return makeLotSummaryResponse({ source_item_id: 5, ...overrides })
}

async function mountTable(lots: LotSummaryResponse[], permissions: string[] = []) {
  const pinia = createPinia()
  setActivePinia(pinia)
  if (permissions.length) useCurrentUserStore().user = userWithPermissions(permissions)

  const lotsStore = useProductionLotsStore()
  lotsStore.items = lots
  lotsStore.total = lots.length

  const router = makeTestRouter()
  await router.push('/')
  await router.isReady()

  const wrapper = mountWithApp(LotsTable, {
    pinia,
    attachTo: document.body,
    props: {
      first: 0,
      rows: 25,
      showManageOrders: false,
      showManageProduction: false,
      showManageSource: false,
      openDetailById: vi.fn<(id: number) => Promise<void>>().mockResolvedValue(undefined),
    },
    global: {
      plugins: [router],
      directives: { tooltip: Tooltip },
    },
  })
  await flushPromises()
  return { wrapper, lotsStore }
}

function approveButton(wrapper: VueWrapper) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.attributes('aria-label') === t('production.lots.detail.record.sourceApproval.approve'))
}

function rejectButton(wrapper: VueWrapper) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.attributes('aria-label') === t('production.lots.detail.record.sourceApproval.reject'))
}

// The server offers approve and reject on a pending lot, approve alone on
// a rejected one, and neither once the lot is finished; the base permission
// manage:lots is the client's own check.
const PENDING_ACTIONS: LifecycleAction[] = ['approve_source', 'reject_source', 'switch_source']
const REJECTED_ACTIONS: LifecycleAction[] = ['approve_source', 'switch_source']

function pendingLot(overrides: Partial<LotSummaryResponse> = {}): LotSummaryResponse {
  return makeLot({
    id: 7,
    source_approval_status: 'pending',
    input_demand_id: null,
    edit_version: 3,
    actions: PENDING_ACTIONS,
    ...overrides,
  })
}

function rejectedLot(overrides: Partial<LotSummaryResponse> = {}): LotSummaryResponse {
  return makeLot({
    id: 8,
    source_approval_status: 'rejected',
    input_demand_id: null,
    source_rejection_reason: 'Wrong material dimension',
    actions: REJECTED_ACTIONS,
    ...overrides,
  })
}

describe('LotsTable source approval column', () => {
  it('pending row, manage:lots: renders Approve/Reject, no pending tag', async () => {
    const { wrapper } = await mountTable([pendingLot()], ['manage:lots'])

    expect(wrapper.find('.approval-cell [data-testid="source-approval-tag"]').exists()).toBe(false)
    expect(approveButton(wrapper)!.attributes('disabled')).toBeUndefined()
    expect(rejectButton(wrapper)!.attributes('disabled')).toBeUndefined()

    wrapper.unmount()
  })

  // click.stop on the row-embedded action buttons: approving must not also
  // open the lot the row would otherwise open on click.
  it('clicking Approve sends the edit version read, triggers a lots refresh, and does not open the row', async () => {
    postMock.mockClear()
    postMock.mockResolvedValue({ data: {} })

    const { wrapper, lotsStore } = await mountTable([pendingLot()], ['manage:lots'])
    const refreshBefore = lotsStore.refreshTrigger

    await approveButton(wrapper)!.trigger('click')
    await flushPromises()

    expect(postMock).toHaveBeenCalledWith('/production-lots/7/source/approve', {
      expected_edit_version: 3,
    })
    expect(lotsStore.refreshTrigger).toBe(refreshBefore + 1)
    expect(wrapper.emitted('open-lot')).toBeFalsy()

    wrapper.unmount()
  })

  it('refreshes the list when Approve meets a 409 from a lot changed elsewhere', async () => {
    postMock.mockClear()
    postMock.mockRejectedValueOnce({
      isAxiosError: true,
      response: { status: 409, data: { detail: 'The lot was changed by someone else.' } },
    })

    const { wrapper, lotsStore } = await mountTable([pendingLot()], ['manage:lots'])
    const refreshBefore = lotsStore.refreshTrigger

    await approveButton(wrapper)!.trigger('click')
    await flushPromises()

    expect(lotsStore.refreshTrigger).toBe(refreshBefore + 1)

    wrapper.unmount()
  })

  it('pending row, no manage:lots: renders the tag and disabled Approve/Reject', async () => {
    const { wrapper } = await mountTable([pendingLot()])

    const tag = wrapper.get('.approval-cell [data-testid="source-approval-tag"]')
    expect(tag.text()).toBe(t('production.lots.detail.record.sourceApproval.pending'))
    expect(approveButton(wrapper)!.attributes('disabled')).toBeDefined()
    expect(rejectButton(wrapper)!.attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  it('pending row on a finished lot: the tag only, the server offers no decision', async () => {
    const { wrapper } = await mountTable([pendingLot({ status: 'canceled', actions: [] })], ['manage:lots'])

    const tag = wrapper.get('.approval-cell [data-testid="source-approval-tag"]')
    expect(tag.text()).toBe(t('production.lots.detail.record.sourceApproval.pending'))
    expect(approveButton(wrapper)).toBeUndefined()
    expect(rejectButton(wrapper)).toBeUndefined()

    wrapper.unmount()
  })

  it('rejected row: renders the Rejected tag, and Approve (not Reject) for a manager', async () => {
    const { wrapper } = await mountTable([rejectedLot()], ['manage:lots'])

    const tags = wrapper.findAll('.approval-cell [data-testid="source-approval-tag"]')
    expect(tags.some((tag) => tag.text() === t('production.lots.detail.record.sourceApproval.rejected'))).toBe(
      true,
    )
    expect(approveButton(wrapper)!.attributes('disabled')).toBeUndefined()
    expect(rejectButton(wrapper)).toBeUndefined()

    wrapper.unmount()
  })

  it('rejected row, no manage:lots: renders the tag and a disabled Approve', async () => {
    const { wrapper } = await mountTable([rejectedLot()])

    const tag = wrapper.get('.approval-cell [data-testid="source-approval-tag"]')
    expect(tag.text()).toBe(t('production.lots.detail.record.sourceApproval.rejected'))
    expect(approveButton(wrapper)!.attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })
})
