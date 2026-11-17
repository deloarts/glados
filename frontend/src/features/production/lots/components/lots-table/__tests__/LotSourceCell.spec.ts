import { describe, it, expect } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeLotSummaryResponse } from '@/test-utils/factories'

import LotSourceCell from '../LotSourceCell.vue'
import type { LotSummaryResponse } from '../../../../types/productionLotsResponse'

// LotsTable.vue renders this cell in both the Simple Mode `source` column and
// the Column/Widescreen Mode `sourceItem` column. Both
// contexts pass the same resolved lot through `lotOf(data)`, so this
// component only ever sees an already-resolved LotSummaryResponse, so there is
// nothing mode-specific left to test, exercising it here covers both
// call sites in LotsTable.vue identically.

function mountCell(lot: LotSummaryResponse) {
  return mountWithApp(LotSourceCell, {
    props: { lot },
    global: {
      directives: { tooltip: Tooltip },
    },
  })
}

describe('LotSourceCell', () => {
  it('renders the alteration tag and nothing else when the lot is an alteration', () => {
    setActivePinia(createPinia())
    const wrapper = mountCell(
      makeLotSummaryResponse({ is_alteration: true, source_label: 'Should be ignored' }),
    )

    const tag = wrapper.findComponent({ name: 'Tag' })
    expect(tag.exists()).toBe(true)
    expect(tag.text()).toBe('Alteration')
    expect(wrapper.find('.source-label').exists()).toBe(false)
  })

  it('renders the source label and sublabel when the lot has a source', () => {
    setActivePinia(createPinia())
    const wrapper = mountCell(
      makeLotSummaryResponse({ source_label: 'Steel bar 20mm', source_sublabel: 'SRC-42' }),
    )

    expect(wrapper.find('.source-label').text()).toBe('Steel bar 20mm')
    expect(wrapper.find('.source-sublabel').text()).toBe('SRC-42')
    expect(wrapper.findComponent({ name: 'Tag' }).exists()).toBe(false)
  })

  it('flags a material mismatch with a tooltip icon when the source material differs', () => {
    setActivePinia(createPinia())
    const wrapper = mountCell(
      makeLotSummaryResponse({
        source_label: 'Steel bar 20mm',
        made_item_material: '1.0037',
        source_material: '1.4301',
      }),
    )

    const warning = wrapper.find('i.source-material-warning')
    expect(warning.exists()).toBe(true)
    expect(warning.attributes('data-pd-tooltip')).toBe('true')
  })

  it('shows no mismatch icon when the source material matches the item material', () => {
    setActivePinia(createPinia())
    const wrapper = mountCell(
      makeLotSummaryResponse({
        source_label: 'Steel bar 20mm',
        made_item_material: '1.0037',
        source_material: '1.0037',
      }),
    )

    expect(wrapper.find('i.source-material-warning').exists()).toBe(false)
  })

  it('shows no mismatch icon when the source has no comparable material', () => {
    setActivePinia(createPinia())
    const wrapper = mountCell(
      makeLotSummaryResponse({
        source_label: 'Bought item ABC',
        made_item_material: '1.0037',
        source_material: undefined,
      }),
    )

    expect(wrapper.find('i.source-material-warning').exists()).toBe(false)
  })

  it('renders the empty placeholder when neither an alteration nor a source is set', () => {
    setActivePinia(createPinia())
    const wrapper = mountCell(makeLotSummaryResponse({ source_label: '', is_alteration: false }))

    expect(wrapper.find('.source-label').text()).toBe('-')
    expect(wrapper.findComponent({ name: 'Tag' }).exists()).toBe(false)
  })
})
