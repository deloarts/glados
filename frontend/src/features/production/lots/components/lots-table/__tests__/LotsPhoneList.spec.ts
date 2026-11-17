import { describe, expect, it } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeLotSummaryResponse } from '@/test-utils/factories'
import { useProductionLotsStore } from '../../../../stores/productionLotsStore'
import LotsPhoneList from '../LotsPhoneList.vue'

async function mountList() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useProductionLotsStore()
  store.items = [
    makeLotSummaryResponse({ id: 7, lot_number: 'LOT-7', target_date: '2026-12-01' }),
  ]
  store.total = 1

  const wrapper = mountWithApp(LotsPhoneList, { pinia, props: { first: 0, rows: 25 } })
  await flushPromises()
  return wrapper
}

describe('LotsPhoneList', () => {
  it('shows only the row number, the lot with its item, the status and the delivery date', async () => {
    const wrapper = await mountList()

    expect(wrapper.findAll('thead th')).toHaveLength(4)
    const cells = wrapper.findAll('tbody tr td')
    expect(cells).toHaveLength(4)
    expect(cells[0]!.text()).toBe('1')
    expect(cells[1]!.text()).toContain('LOT-7')
    expect(cells[1]!.text()).toContain('Bracket')

    wrapper.unmount()
  })

  it('opens the lot a row is tapped on', async () => {
    const wrapper = await mountList()

    await wrapper.get('tbody tr').trigger('click')

    const opened = wrapper.emitted('open-lot')
    expect(opened).toHaveLength(1)
    expect(opened![0]![0]).toMatchObject({ id: 7 })

    wrapper.unmount()
  })
})
