import { describe, it, expect } from 'vitest'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeLotSummaryResponse } from '@/test-utils/factories'
import { formatDateOrDash } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

import LotRequiredDeliveryDateCell from '../LotRequiredDeliveryDateCell.vue'
import type { LotSummaryResponse } from '../../../../types/productionLotsResponse'

// The cell went from an editable DatePicker to plain read-only text with a
// provenance note underneath (editing moved to the row context menu, see
// LotRequiredDeliveryDateDialog.vue). This covers the date text, the note
// per target_date_source, and the red-if-late class.

function makeLot(overrides: Partial<LotSummaryResponse> = {}): LotSummaryResponse {
  return makeLotSummaryResponse({
    target_date: null,
    target_date_source: null,
    target_date_demand_item_id: null,
    ...overrides,
  })
}

function mountCell(lot: LotSummaryResponse, hasPastTargetDateConflict = false) {
  return mountWithApp(LotRequiredDeliveryDateCell, {
    props: { lot, hasPastTargetDateConflict },
    global: { directives: { tooltip: Tooltip } },
  })
}

describe('LotRequiredDeliveryDateCell', () => {
  it('renders the resolved target date, not the raw required_delivery_date', () => {
    const wrapper = mountCell(
      makeLot({
        required_delivery_date: '2026-03-01',
        target_date: '2026-04-15',
        target_date_source: 'lot',
      }),
    )

    expect(wrapper.text()).toContain(formatDateOrDash('2026-04-15'))
  })

  it('shows the empty placeholder and no note when there is no target date', () => {
    const wrapper = mountCell(makeLot())

    expect(wrapper.text()).toContain(getEmptyPlaceholder())
    expect(wrapper.find('.required-delivery-note').exists()).toBe(false)
  })

  it('shows the manual-date note when the source is the lot itself', () => {
    const wrapper = mountCell(
      makeLot({ target_date: '2026-04-15', target_date_source: 'lot' }),
    )

    expect(wrapper.find('.required-delivery-note').text()).toBe('Set on the lot')
  })

  it('shows the demand-derived note with the demand item id when the source is a demand', () => {
    const wrapper = mountCell(
      makeLot({
        target_date: '2026-05-01',
        target_date_source: 'demand',
        target_date_demand_item_id: 42,
      }),
    )

    expect(wrapper.find('.required-delivery-note').text()).toBe(
      'From demand #42, earliest desired delivery',
    )
  })

  it('applies the red-if-late class only when hasPastTargetDateConflict is true', () => {
    const lot = makeLot({ target_date: '2026-04-15', target_date_source: 'lot' })

    const late = mountCell(lot, true)
    expect(late.find('.required-delivery-date--late').exists()).toBe(true)

    const onTime = mountCell(lot, false)
    expect(onTime.find('.required-delivery-date--late').exists()).toBe(false)
  })
})
