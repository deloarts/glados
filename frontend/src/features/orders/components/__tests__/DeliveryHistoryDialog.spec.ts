import { describe, it, expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeOrderItemResponse } from '@/test-utils/factories'

import DeliveryHistoryDialog from '../DeliveryHistoryDialog.vue'
import type { DeliveryRecord, OrderItemResponse } from '../../types/ordersResponse'

function makeRecord(overrides: Partial<DeliveryRecord> = {}): DeliveryRecord {
  return {
    id: 1,
    public_id: 'cccccccc-0000-0000-0000-000000000001',
    delivery_date: '2026-02-01T10:00:00Z',
    quantity: 1,
    quantity_rejected: 0,
    rejection_reason: null,
    rejection_note: null,
    rejection_outcome: null,
    storage_place: null,
    receiver_id: null,
    receiver: null,
    correction_reason: null,
    supplier_batch: null,
    delivery_note_number: null,
    certificate_reference: null,
    corrects_delivery_id: null,
    damage_noted_on_delivery_note: false,
    ...overrides,
  }
}

function makeItem(records: DeliveryRecord[]): OrderItemResponse {
  return makeOrderItemResponse({
    status: 'partially_delivered',
    quantity_delivered: 1,
    quantity_rejected: 0,
    quantity_rejected_lost: 0,
    price: null,
    delivery_records: records,
  })
}

async function mountDialog(item: OrderItemResponse) {
  const wrapper = mountWithApp(DeliveryHistoryDialog, {
    attachTo: document.body,
    props: { visible: true, item },
  })
  await flushPromises()
  return wrapper
}

describe('DeliveryHistoryDialog', () => {
  it('renders rejected quantity, reason and outcome for a record with a rejection', async () => {
    const record = makeRecord({
      quantity: 1,
      quantity_rejected: 1,
      rejection_reason: 'supplier_damage',
      rejection_outcome: 'lost',
    })
    const wrapper = await mountDialog(makeItem([record]))

    expect(document.body.textContent).toContain('Supplier Damage')
    expect(document.body.textContent).toContain('Piece is lost')

    wrapper.unmount()
  })

  it('shows the redeliver outcome label for a record rejected with that outcome', async () => {
    const record = makeRecord({
      quantity: 1,
      quantity_rejected: 1,
      rejection_reason: 'transport_damage',
      rejection_outcome: 'redeliver',
    })
    const wrapper = await mountDialog(makeItem([record]))

    expect(document.body.textContent).toContain('Transport Damage')
    expect(document.body.textContent).toContain('Supplier re-delivers')

    wrapper.unmount()
  })

  it('does not render a rejection reason or outcome for a plain delivery record', async () => {
    const record = makeRecord({ quantity: 2 })
    const wrapper = await mountDialog(makeItem([record]))

    expect(document.body.textContent).not.toContain('Supplier Damage')
    expect(document.body.textContent).not.toContain('Piece is lost')
    expect(document.body.textContent).not.toContain('Supplier re-delivers')

    wrapper.unmount()
  })
})
