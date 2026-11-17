import { describe, it, expect, vi, beforeEach } from 'vitest'

import type { SupplierMailRecipientsResponse } from '../types/contactResponse'

const recipientsMock = vi.fn<(id: number) => Promise<SupplierMailRecipientsResponse>>()
vi.mock('../api/contactsApi', () => ({
  getSupplierMailRecipients: (id: number) => recipientsMock(id),
}))

import { flaggedSupplierRecipients } from '../utils/supplierMailRecipients'

beforeEach(() => {
  recipientsMock.mockReset()
})

describe('flaggedSupplierRecipients', () => {
  it('joins the flagged addresses of the mail kind', async () => {
    recipientsMock.mockResolvedValue({
      supplier_id: 3,
      request: [
        { contact_id: 1, name: 'Karin', email: 'karin@example.com' },
        { contact_id: 2, name: 'Martin', email: 'martin@example.com' },
      ],
      order: [],
    })

    expect(await flaggedSupplierRecipients(3, 'request')).toBe('karin@example.com, martin@example.com')
    expect(await flaggedSupplierRecipients(3, 'order')).toBeNull()
  })

  it('answers null when the lookup fails, so the supplier address applies', async () => {
    recipientsMock.mockImplementation(async () => {
      throw new Error('403')
    })

    expect(await flaggedSupplierRecipients(3, 'order')).toBeNull()
  })
})
