import { describe, it, expect, vi, beforeEach } from 'vitest'
import { defineComponent, h } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeOrderResponse, makeUserResponse } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import type { SupplierMailKind } from '@/features/contacts'
import type { SupplierResponse } from '@/features/suppliers'

// The To field of a supplier mail: the supplier's contacts flagged for the
// mail kind, and the supplier's own addresses when none is flagged, so a
// supplier without contacts keeps its recipients.

const getSupplierMock = vi.fn<(id: number) => Promise<SupplierResponse>>()
vi.mock('@/features/suppliers', () => ({
  getSupplier: (id: number) => getSupplierMock(id),
}))

const flaggedMock = vi.fn<(id: number, kind: SupplierMailKind) => Promise<string | null>>()
vi.mock('@/features/contacts', () => ({
  flaggedSupplierRecipients: (id: number, kind: SupplierMailKind) => flaggedMock(id, kind),
}))

vi.mock('openvue/usetoast', () => ({
  useToast: () => ({ add: vi.fn<(message: unknown) => void>() }),
}))

import { useOrderMailComposer } from '../useOrderMailComposer'

function makeSupplier(overrides: Partial<SupplierResponse> = {}): SupplierResponse {
  return {
    edit_version: 0,
    id: 5,
    public_id: '44444444-4444-4444-4444-444444444444',
    created: '2026-01-01T00:00:00Z',
    changed: '2026-01-01T00:00:00Z',
    changed_by_id: null,
    changed_by: null,
    archived: false,
    name: 'Sample Supplier Ltd',
    legal_name: null,
    vat_id: null,
    level: 'B',
    capability_ids: [],
    capabilities: [],
    article_group_ids: [],
    article_groups: [],
    street: null,
    city: null,
    country: null,
    postal_code: null,
    email: 'contact@supplier.example',
    phone: null,
    weblink: null,
    order_email: null,
    order_language: null,
    order_template: null,
    request_email: null,
    request_language: null,
    request_template: null,
    edp_type_number_first: false,
    creator_id: 1,
    creator: null,
    edp_code: null,
    external_lead_time_days: null,
    ...overrides,
  }
}

function mountComposable() {
  let result!: ReturnType<typeof useOrderMailComposer>
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = makeUserResponse({
    full_name: 'Jane Smith',
    email: 'jane.smith@example.com',
  })

  const wrapper = mountWithApp(
    defineComponent({
      setup() {
        result = useOrderMailComposer()
        return () => h('div')
      },
    }),
    { pinia },
  )
  return { result, wrapper }
}

describe('useOrderMailComposer recipients', () => {
  beforeEach(() => {
    getSupplierMock.mockReset()
    flaggedMock.mockReset()
  })

  it('fills To from the contacts flagged for order mails', async () => {
    getSupplierMock.mockResolvedValue(
      makeSupplier({ order_template: 'Hi', order_email: 'orders@supplier.example' }),
    )
    flaggedMock.mockResolvedValue('karin@supplier.example, eva@supplier.example')
    const { result } = mountComposable()

    await result.composeOrderMail(makeOrderResponse(), 'order')

    expect(flaggedMock).toHaveBeenCalledWith(5, 'order')
    expect(result.dialogState.to).toBe('karin@supplier.example, eva@supplier.example')
  })

  it('asks for the request contacts on a request mail', async () => {
    getSupplierMock.mockResolvedValue(makeSupplier({ order_template: 'Hi', request_template: 'Hi' }))
    flaggedMock.mockResolvedValue(null)
    const { result } = mountComposable()

    await result.composeOrderMail(makeOrderResponse(), 'request')
    expect(flaggedMock).toHaveBeenLastCalledWith(5, 'request')
  })

  it("falls back to the supplier's own addresses when no contact is flagged", async () => {
    getSupplierMock.mockResolvedValue(
      makeSupplier({
        order_template: 'Hi',
        request_template: 'Hi',
        order_email: 'orders@supplier.example',
        request_email: 'requests@supplier.example',
      }),
    )
    flaggedMock.mockResolvedValue(null)
    const { result } = mountComposable()

    await result.composeOrderMail(makeOrderResponse(), 'order')
    expect(result.dialogState.to).toBe('orders@supplier.example')

    await result.composeOrderMail(makeOrderResponse(), 'request')
    expect(result.dialogState.to).toBe('requests@supplier.example')
  })
})
