import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'

import type { LotMaterialReceiptResponse } from '../../../../types/productionLotsResponse'

const getLotMaterialReceipts = vi.hoisted(() =>
  vi.fn<(id: number) => Promise<LotMaterialReceiptResponse[]>>(),
)

vi.mock('../../../api/getLotMaterialReceipts', () => ({ getLotMaterialReceipts }))

import LotRecordMaterialReceipts from '../LotRecordMaterialReceipts.vue'

const RECEIPT: LotMaterialReceiptResponse = {
  delivery_id: 5,
  order_item_id: 3,
  order_id: 2,
  order_number: 'ORD-0002',
  delivery_date: '2026-10-20T08:00:00Z',
  quantity: 5,
  supplier_batch: 'H-4711',
  delivery_note_number: 'LS-118',
  certificate_reference: '3.1-99812',
  corrects_delivery_id: null,
}

describe('LotRecordMaterialReceipts', () => {
  beforeEach(() => getLotMaterialReceipts.mockReset())

  it('lists each receipt with its batch, delivery note and certificate', async () => {
    getLotMaterialReceipts.mockResolvedValue([RECEIPT])

    const wrapper = mountWithApp(LotRecordMaterialReceipts, { props: { lotId: 7 } })
    await flushPromises()

    expect(getLotMaterialReceipts).toHaveBeenCalledWith(7)
    const row = wrapper.find('tbody tr').text()
    expect(row).toContain('ORD-0002')
    expect(row).toContain('H-4711')
    expect(row).toContain('LS-118')
    expect(row).toContain('3.1-99812')

    wrapper.unmount()
  })

  it('says so when the raw material has not arrived', async () => {
    getLotMaterialReceipts.mockResolvedValue([])

    const wrapper = mountWithApp(LotRecordMaterialReceipts, { props: { lotId: 7 } })
    await flushPromises()

    expect(wrapper.text()).toContain(
      i18n.global.t('production.lots.detail.record.materialReceipts.none'),
    )

    wrapper.unmount()
  })
})
