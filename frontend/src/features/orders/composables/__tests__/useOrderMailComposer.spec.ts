import { describe, it, expect, vi, beforeEach } from 'vitest'
import { defineComponent, h } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeOrderResponse, makeUserResponse } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import type { SupplierResponse } from '@/features/suppliers'
import type { DefaultMailTemplateResult } from '../../api/getDefaultMailTemplate'

// Mirrors useOrderDocketDownload.spec.ts's mock-toast + mountComposable
// pattern. Covers the fallback rework in useOrderMailComposer.ts: a
// supplier's own template still wins; missing it, the tenant-wide admin
// default is fetched with the supplier's own language; an unconfigured (or
// failed) fallback still surfaces the accurate "no template configured"
// warning rather than the generic error toast.

const getSupplierMock = vi.fn<(id: number) => Promise<SupplierResponse>>()
vi.mock('@/features/suppliers', () => ({
  getSupplier: (id: number) => getSupplierMock(id),
}))

const getDefaultMailTemplateMock =
  vi.fn<(kind: string, language: string | null) => Promise<DefaultMailTemplateResult>>()
vi.mock('../../api/getDefaultMailTemplate', () => ({
  getDefaultMailTemplate: (kind: string, language: string | null) =>
    getDefaultMailTemplateMock(kind, language),
}))

const toastAddMock = vi.fn<(message: unknown) => void>()
vi.mock('openvue/usetoast', () => ({
  useToast: () => ({ add: toastAddMock }),
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

describe('useOrderMailComposer', () => {
  beforeEach(() => {
    getSupplierMock.mockReset()
    getDefaultMailTemplateMock.mockReset()
    toastAddMock.mockReset()
  })

  it("uses the supplier's own template when present, without ever fetching the admin default", async () => {
    getSupplierMock.mockResolvedValue(
      makeSupplier({ order_template: 'Hi {{ supplier }}', order_language: 'de' }),
    )
    const { result } = mountComposable()

    await result.composeOrderMail(makeOrderResponse(), 'order')

    expect(result.dialogVisible.value).toBe(true)
    expect(result.dialogState.body).toContain('Sample Supplier Ltd')
    expect(getDefaultMailTemplateMock).not.toHaveBeenCalled()
    expect(toastAddMock).not.toHaveBeenCalled()
  })

  it("falls back to the tenant admin default with the supplier's own language when no supplier template exists", async () => {
    getSupplierMock.mockResolvedValue(makeSupplier({ order_template: null, order_language: 'fr' }))
    getDefaultMailTemplateMock.mockResolvedValue({
      kind: 'order',
      language: 'fr',
      subject: 'Default subject',
      body: 'Default: {{ supplier }}',
      configured: true,
    })
    const { result } = mountComposable()

    await result.composeOrderMail(makeOrderResponse(), 'order')

    expect(getDefaultMailTemplateMock).toHaveBeenCalledWith('order', 'fr')
    expect(result.dialogVisible.value).toBe(true)
    expect(result.dialogState.body).toContain('Default:')
    expect(result.dialogState.body).toContain('Sample Supplier Ltd')
  })

  it('shows the no-template warning (not an error) when the admin default comes back unconfigured', async () => {
    getSupplierMock.mockResolvedValue(makeSupplier({ order_template: null }))
    getDefaultMailTemplateMock.mockResolvedValue({
      kind: 'order',
      language: 'enGB',
      subject: '',
      body: '',
      configured: false,
    })
    const { result } = mountComposable()

    await result.composeOrderMail(makeOrderResponse(), 'order')

    expect(result.dialogVisible.value).toBe(false)
    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'warn' }),
    )
    expect(toastAddMock).not.toHaveBeenCalledWith(expect.objectContaining({ severity: 'error' }))
  })

  it('shows the no-template warning (not the generic error) when the admin-default lookup itself fails', async () => {
    getSupplierMock.mockResolvedValue(makeSupplier({ order_template: null }))
    getDefaultMailTemplateMock.mockRejectedValue(new Error('network down'))
    const { result } = mountComposable()

    await result.composeOrderMail(makeOrderResponse(), 'order')

    expect(result.dialogVisible.value).toBe(false)
    expect(toastAddMock).toHaveBeenCalledTimes(1)
    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'warn' }),
    )
  })

  describe('supplier_order_numbers', () => {
    async function bodyFor(numbers: string[]): Promise<string> {
      getSupplierMock.mockResolvedValue(makeSupplier({ order_email: 'orders@supplier.example' }))
      getDefaultMailTemplateMock.mockResolvedValue({
        kind: 'order_canceled',
        language: 'en',
        subject: 'Subject',
        body: 'Your reference: {{ supplier_order_numbers }}.',
        configured: true,
      })
      const { result } = mountComposable()
      await result.composeOrderMail(
        makeOrderResponse({ supplier_order_numbers: numbers }),
        'order_canceled',
      )
      return result.dialogState.body
    }

    it('lists the numbers separated by commas', async () => {
      expect(await bodyFor(['AB-24117', 'AB-24131'])).toContain('Your reference: AB-24117, AB-24131.')
    })

    it('puts the empty value symbol in for an order without one', async () => {
      expect(await bodyFor([])).toContain(`Your reference: ${getEmptyPlaceholder()}.`)
    })
  })

  // order_canceled has no per-supplier override column at all (see supplierResponse.ts),
  // so every cancellation mail must go through the tenant-wide admin default, never a
  // supplier's own order_template.
  describe('order_canceled (no per-supplier override exists)', () => {
    it('ignores a configured supplier order_template and opens the dialog with the resolved admin default', async () => {
      getSupplierMock.mockResolvedValue(
        makeSupplier({
          // Deliberately set, to prove it's never read for this type.
          order_template: 'Hi {{ supplier }}, your order was ordered.',
          order_email: 'orders@supplier.example',
          order_language: 'fr',
        }),
      )
      getDefaultMailTemplateMock.mockResolvedValue({
        kind: 'order_canceled',
        language: 'fr',
        subject: 'Default subject',
        body: 'Sorry, {{ order_number }} for {{ supplier }} was canceled.',
        configured: true,
      })
      const { result } = mountComposable()

      await result.composeOrderMail(makeOrderResponse({ order_number: 'ORD-42' }), 'order_canceled')

      // The per-supplier template was never consulted for this type: the admin default
      // is fetched unconditionally, with the supplier's own order_language
      // (order_canceled has no request/order distinction of its own to make).
      expect(getDefaultMailTemplateMock).toHaveBeenCalledWith('order_canceled', 'fr')
      expect(result.dialogVisible.value).toBe(true)
      expect(result.dialogState.body).toContain('ORD-42')
      expect(result.dialogState.body).toContain('Sample Supplier Ltd')
      expect(result.dialogState.body).not.toContain('was ordered')
      expect(result.dialogState.to).toBe('orders@supplier.example')
      expect(toastAddMock).not.toHaveBeenCalled()
    })

    it('shows the no-template warning when no admin default is configured for order_canceled', async () => {
      getSupplierMock.mockResolvedValue(makeSupplier({ order_template: null }))
      getDefaultMailTemplateMock.mockResolvedValue({
        kind: 'order_canceled',
        language: 'enGB',
        subject: '',
        body: '',
        configured: false,
      })
      const { result } = mountComposable()

      await result.composeOrderMail(makeOrderResponse(), 'order_canceled')

      expect(getDefaultMailTemplateMock).toHaveBeenCalledWith('order_canceled', null)
      expect(result.dialogVisible.value).toBe(false)
      expect(toastAddMock).toHaveBeenCalledWith(expect.objectContaining({ severity: 'warn' }))
      expect(toastAddMock).not.toHaveBeenCalledWith(expect.objectContaining({ severity: 'error' }))
    })
  })

  describe('the follow-up after sending', () => {
    it.each(['request', 'order'] as const)(
      'offers to mark the lines after a %s mail',
      async (type) => {
        getSupplierMock.mockResolvedValue(
          makeSupplier({ order_template: 'Hi', request_template: 'Hi' }),
        )
        const { result } = mountComposable()

        await result.composeOrderMail(makeOrderResponse(), type)
        result.onMailSent()

        expect(result.showPostSend.value).toBe(true)
      },
    )

    it('offers nothing to mark after a cancellation notice', async () => {
      getSupplierMock.mockResolvedValue(makeSupplier())
      getDefaultMailTemplateMock.mockResolvedValue({
        kind: 'order_canceled',
        language: 'enGB',
        subject: '',
        body: 'Canceled',
        configured: true,
      })
      const { result } = mountComposable()

      await result.composeOrderMail(makeOrderResponse(), 'order_canceled')
      result.onMailSent()

      expect(result.showPostSend.value).toBe(false)
    })
  })
})
