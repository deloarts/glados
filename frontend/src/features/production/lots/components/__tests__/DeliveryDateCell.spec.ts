import { describe, it, expect } from 'vitest'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'

import DeliveryDateCell from '../DeliveryDateCell.vue'

import type { PlannedStepInfo } from '../DeliveryDateCell.vue'
import type { PlannedDateEditTarget } from '../../../composables/useLotStepDeliveryInfo'

// LotStepList.vue renders this cell in both the Planned-Start and
// Planned-Date columns, which differ only in which field of the caller's
// plannedInfoFor() result each column shows. The `infoKey` prop picks that
// field.

const EDIT_TARGET: PlannedDateEditTarget = {
  kind: 'internal',
  orderId: 42,
  editVersion: 0,
  currentPlannedStart: '2026-08-01T00:00:00Z',
  currentPlannedEnd: '2026-08-05T00:00:00Z',
  lotId: 1,
  madeItem: { id: 1, partNumber: 'PN-1', revision: 'A', articleName: 'Bracket' },
  thisStep: { fabricationMethodName: 'Milling' },
  prevStep: null,
  nextStep: null,
}

function makeInfo(overrides: Partial<PlannedStepInfo> = {}): PlannedStepInfo {
  return {
    date: null,
    startDate: null,
    plannedByLabel: null,
    ...overrides,
  }
}

function mountCell(props: {
  info: PlannedStepInfo
  infoKey: 'date' | 'startDate'
  editTarget: PlannedDateEditTarget
}) {
  return mountWithApp(DeliveryDateCell, {
    props,
    global: { directives: { tooltip: Tooltip } },
  })
}

describe('DeliveryDateCell', () => {
  it('renders the formatted date picked by infoKey, ignoring the other field', () => {
    const info = makeInfo({ date: new Date(2026, 7, 15), startDate: new Date(2026, 7, 10) })

    const dateWrapper = mountCell({ info, infoKey: 'date', editTarget: null })
    expect(dateWrapper.find('.delivery-date-row').text()).toContain('2026-08-15')

    const startWrapper = mountCell({ info, infoKey: 'startDate', editTarget: null })
    expect(startWrapper.find('.delivery-date-row').text()).toContain('2026-08-10')
  })

  it('renders the empty placeholder when the picked field is null', () => {
    const wrapper = mountCell({ info: makeInfo(), infoKey: 'date', editTarget: null })
    expect(wrapper.find('.delivery-date-row').text()).toBe('-')
  })

  it('renders the planned-by note when present', () => {
    const wrapper = mountCell({
      info: makeInfo({ date: new Date(2026, 7, 15), plannedByLabel: 'Auto planner' }),
      infoKey: 'date',
      editTarget: null,
    })
    expect(wrapper.find('.delivery-note').text()).toBe('Auto planner')
  })

  it('omits the planned-by note when absent', () => {
    const wrapper = mountCell({ info: makeInfo(), infoKey: 'date', editTarget: null })
    expect(wrapper.find('.delivery-note').exists()).toBe(false)
  })

  it('hides the edit button when there is no edit target (readonly or unassignable)', () => {
    const wrapper = mountCell({ info: makeInfo(), infoKey: 'date', editTarget: null })
    expect(wrapper.findComponent({ name: 'Button' }).exists()).toBe(false)
  })

  it('shows the edit button and emits it back on click when an edit target is given', async () => {
    const wrapper = mountCell({ info: makeInfo(), infoKey: 'date', editTarget: EDIT_TARGET })

    const button = wrapper.findComponent({ name: 'Button' })
    expect(button.exists()).toBe(true)
    await button.trigger('click')

    expect(wrapper.emitted('edit')).toEqual([[EDIT_TARGET]])
  })
})
