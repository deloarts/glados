import { describe, it, expect } from 'vitest'
import { type VueWrapper } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { makeLotResponse, makeSourceItemDemandResponse } from '@/test-utils/factories'

import LotRecordSourceDemand from '../lot-detail/LotRecordSourceDemand.vue'
import type { LotResponse } from '../../../types/productionLotsResponse'
import type { SourceItemDemandResponse } from '@/features/source-items'

// Same shape/defaults as the existing LotRecordSourceDemand.spec.ts's local
// makeLot, duplicated rather than imported since that file is read-only and
// this one, so keeping the two in lockstep by hand.
function makeLot(overrides: Partial<LotResponse> = {}): LotResponse {
  return makeLotResponse({
    public_id: '3f2504e0-4f89-11d3-9a0c-0305e82c3301',
    quantity_completed: 0,
    status: 'draft',
    ...overrides,
  })
}

// Same shape as lotStateSummary.spec.ts's local makeDemand.
function makeDemand(overrides: Partial<SourceItemDemandResponse> = {}): SourceItemDemandResponse {
  return makeSourceItemDemandResponse({
    id: 9,
    public_id: '99999999-9999-9999-9999-999999999999',
    status: 'ordered',
    created: '2026-07-01',
    quantity: 10,
    unit: 'kg',
    source_item_id: 5,
    source_item: null,
    project_id: 42,
    project_description: '',
    ...overrides,
  })
}

function mountDemand(
  lot: LotResponse,
  options: {
    manageMode?: boolean
    canWrite?: boolean
    canApprove?: boolean
    sourceItemDemand?: SourceItemDemandResponse | null
  } = {},
) {
  return mountWithApp(LotRecordSourceDemand, {
    attachTo: document.body,
    props: {
      lot,
      sourceItemDemand: options.sourceItemDemand ?? null,
      sourceItemDemandArrived: 0,
      summary: null,
      allocations: [],
      sourceOrder: null,
      manageMode: options.manageMode ?? false,
      canWrite: options.canWrite ?? false,
      canApprove: options.canApprove ?? false,
    },
  })
}

const t = (key: string): string => i18n.global.t(key) as string

function findButton(wrapper: VueWrapper, label: string) {
  return wrapper.findAllComponents({ name: 'Button' }).find((b) => b.props('label') === label)
}

describe('LotRecordSourceDemand source approval', () => {
  describe('pending, no demand yet', () => {
    it('without manage:lots: shows the Approval Required tag and the no-demand hint, no Approve/Reject buttons', () => {
      const wrapper = mountDemand(
        makeLot({ source_approval_status: 'pending', source_item_id: 5, input_demand_id: null }),
        { manageMode: false, canWrite: false, canApprove: false },
      )

      const tag = wrapper.get('.approval-tag')
      expect(tag.text()).toBe(t('production.lots.detail.record.sourceApproval.pending'))
      expect(wrapper.text()).toContain(
        t('production.lots.detail.record.sourceApproval.noDemandUntilApproved'),
      )
      expect(findButton(wrapper, t('production.lots.detail.record.sourceApproval.approve'))).toBeUndefined()
      expect(findButton(wrapper, t('production.lots.detail.record.sourceApproval.reject'))).toBeUndefined()

      wrapper.unmount()
    })

    it('with manage:lots: shows Approve/Reject instead of the tag, and disables "Demand Source Item"', async () => {
      const wrapper = mountDemand(
        makeLot({
          source_approval_status: 'pending',
          source_item_id: 5,
          input_demand_id: null,
          actions: ['approve_source', 'reject_source'],
        }),
        { manageMode: true, canWrite: true, canApprove: true },
      )

      // The tag is an either/or with the buttons, not both at once.
      expect(wrapper.find('.approval-tag').exists()).toBe(false)

      const approveButton = findButton(wrapper, t('production.lots.detail.record.sourceApproval.approve'))
      const rejectButton = findButton(wrapper, t('production.lots.detail.record.sourceApproval.reject'))
      expect(approveButton).toBeDefined()
      expect(rejectButton).toBeDefined()

      await approveButton!.trigger('click')
      expect(wrapper.emitted('approve-source')).toHaveLength(1)

      await rejectButton!.trigger('click')
      expect(wrapper.emitted('reject-source')).toHaveLength(1)

      // canDemandSourceItem(lot) is false while pending, even though this
      // lot otherwise has everything "Demand Source Item" would need (a
      // source item, manageMode, canWrite); the approval gate wins.
      const demandButton = findButton(
        wrapper,
        t('production.lots.detail.rawMaterial.createDemand'),
      )
      expect(demandButton).toBeDefined()
      expect(demandButton!.attributes('disabled')).toBeDefined()

      wrapper.unmount()
    })
  })

  describe('rejected, no demand yet', () => {
    it('shows the Rejected tag and reason, and offers Approve but not Reject', () => {
      const wrapper = mountDemand(
        makeLot({
          source_approval_status: 'rejected',
          source_item_id: 5,
          input_demand_id: null,
          source_rejected_by_id: 2,
          source_rejected_date: '2026-08-01T10:00:00Z',
          source_rejection_reason: 'Wrong material dimension',
          actions: ['approve_source'],
        }),
        { manageMode: false, canWrite: false, canApprove: true },
      )

      const tag = wrapper.get('.approval-tag')
      expect(tag.text()).toBe(t('production.lots.detail.record.sourceApproval.rejected'))
      expect(wrapper.get('.field-note').text()).toBe('Wrong material dimension')
      expect(wrapper.text()).toContain(t('production.lots.detail.record.sourceApproval.rejectedBy'))
      expect(wrapper.text()).toContain(t('production.lots.detail.record.sourceApproval.rejectedOn'))

      expect(
        findButton(wrapper, t('production.lots.detail.record.sourceApproval.approve')),
      ).toBeDefined()
      expect(
        findButton(wrapper, t('production.lots.detail.record.sourceApproval.reject')),
      ).toBeUndefined()

      wrapper.unmount()
    })
  })

  // Regression guard: not_required must render none of the approval UI:
  // only the plain "no demand yet" empty state (and, separately, whatever
  // manageMode's own "Demand Source Item" button does, untouched here).
  describe('not_required', () => {
    it('renders no approval tag, no approval fields, and no Approve/Reject buttons', () => {
      const wrapper = mountDemand(
        makeLot({ source_approval_status: 'not_required', input_demand_id: null }),
        { manageMode: true, canWrite: true, canApprove: true },
      )

      expect(wrapper.find('.approval-tag').exists()).toBe(false)
      expect(wrapper.find('.approval-grid').exists()).toBe(false)
      expect(
        findButton(wrapper, t('production.lots.detail.record.sourceApproval.approve')),
      ).toBeUndefined()
      expect(
        findButton(wrapper, t('production.lots.detail.record.sourceApproval.reject')),
      ).toBeUndefined()

      wrapper.unmount()
    })
  })

  // Reachable only once a prior demand was since canceled: the approval
  // decision survives (cancel_source_item_demand.py clears input_demand_id,
  // not source_approval_status), so this same "no demand yet" section can
  // also show an approved record rather than the empty state.
  describe('approved, no demand yet (demand was canceled)', () => {
    it('shows the approved-by/approved-on record', () => {
      const wrapper = mountDemand(
        makeLot({
          source_approval_status: 'approved',
          input_demand_id: null,
          source_approved_by_id: 3,
          source_approved_date: '2026-08-02T09:00:00Z',
        }),
        { manageMode: false, canWrite: false, canApprove: false },
      )

      expect(wrapper.text()).toContain(t('production.lots.detail.record.sourceApproval.approvedBy'))
      expect(wrapper.text()).toContain(t('production.lots.detail.record.sourceApproval.approvedOn'))

      wrapper.unmount()
    })
  })

  describe('approved, with a demand linked', () => {
    it('shows the approved-by/approved-on record alongside the demand detail', () => {
      const wrapper = mountDemand(
        makeLot({
          source_approval_status: 'approved',
          input_demand_id: 55,
          source_approved_by_id: 3,
          source_approved_date: '2026-08-02T09:00:00Z',
        }),
        { sourceItemDemand: makeDemand({ lot_id: 1 }) },
      )

      expect(wrapper.text()).toContain(t('production.lots.detail.record.sourceApproval.approvedBy'))
      expect(wrapper.text()).toContain(t('production.lots.detail.record.sourceApproval.approvedOn'))

      wrapper.unmount()
    })
  })
})
