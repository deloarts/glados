import { describe, it, expect, vi, beforeEach } from 'vitest'
import { defineComponent, h } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeOrderResponse } from '@/test-utils/factories'

// OrdersTable.vue's docket download (try/catch plus toast), kept out of the
// table's large template.

const downloadPrintTemplateMock =
  vi.fn<(classifier: string, rootType: string, rootId: number) => Promise<{ warnings: string[] }>>()
vi.mock('@/features/print-labels/api/downloadPrintTemplate', () => ({
  downloadPrintTemplate: (classifier: string, rootType: string, rootId: number) =>
    downloadPrintTemplateMock(classifier, rootType, rootId),
}))

const printDocumentsMock =
  vi.fn<(body: unknown) => Promise<{ status: string; error_message: string | null }[]>>()
vi.mock('@/features/print-labels/api/printDocuments', () => ({
  printDocuments: (body: unknown) => printDocumentsMock(body),
}))

const toastAddMock = vi.fn<(message: unknown) => void>()
vi.mock('openvue/usetoast', () => ({
  useToast: () => ({ add: toastAddMock }),
}))

import { useOrderDocketDownload } from '../useOrderDocketDownload'

function mountComposable() {
  let result!: ReturnType<typeof useOrderDocketDownload>
  const wrapper = mountWithApp(
    defineComponent({
      setup() {
        result = useOrderDocketDownload()
        return () => h('div')
      },
    }),
  )
  return { result, wrapper }
}

describe('useOrderDocketDownload', () => {
  beforeEach(() => {
    downloadPrintTemplateMock.mockReset()
    printDocumentsMock.mockReset()
    toastAddMock.mockReset()
  })

  it('starts with no order downloading', () => {
    const { result } = mountComposable()
    expect(result.downloadingDocketId.value).toBeNull()
  })

  it('tracks the downloading order id while the request is in flight, then clears it', async () => {
    let resolve!: (value: { warnings: string[] }) => void
    downloadPrintTemplateMock.mockReturnValue(
      new Promise((r) => {
        resolve = r
      }),
    )
    const { result } = mountComposable()
    const order = makeOrderResponse({ id: 42 })

    const promise = result.downloadOrderDocket(order)
    expect(result.downloadingDocketId.value).toBe(42)

    resolve({ warnings: [] })
    await promise

    expect(result.downloadingDocketId.value).toBeNull()
  })

  it('calls downloadPrintTemplate with the order_docket classifier and the order id', async () => {
    downloadPrintTemplateMock.mockResolvedValue({ warnings: [] })
    const { result } = mountComposable()

    await result.downloadOrderDocket(makeOrderResponse({ id: 7 }))

    expect(downloadPrintTemplateMock).toHaveBeenCalledWith('order_docket', 'order', 7)
  })

  it('shows a warn toast per warning, keyed by the order number', async () => {
    downloadPrintTemplateMock.mockResolvedValue({ warnings: ['Missing supplier VAT id'] })
    const { result } = mountComposable()

    await result.downloadOrderDocket(makeOrderResponse({ order_number: 'ORD-42' }))

    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'warn', summary: 'ORD-42', detail: 'Missing supplier VAT id' }),
    )
  })

  it('shows an error toast and clears the downloading id when the request fails', async () => {
    downloadPrintTemplateMock.mockRejectedValue(new Error('network error'))
    const { result } = mountComposable()

    await result.downloadOrderDocket(makeOrderResponse({ id: 5, order_number: 'ORD-5' }))

    expect(result.downloadingDocketId.value).toBeNull()
    expect(toastAddMock).toHaveBeenCalledWith(expect.objectContaining({ severity: 'error', summary: 'ORD-5' }))
  })

  it('prints the order docket and reports a sent job', async () => {
    printDocumentsMock.mockResolvedValue([{ status: 'sent', error_message: null }])
    const { result } = mountComposable()

    await result.printOrderDocket(makeOrderResponse({ id: 9, order_number: 'ORD-9' }))

    expect(printDocumentsMock).toHaveBeenCalledWith(
      expect.objectContaining({ root_type: 'order', root_id: 9, items: [{ classifier: 'order_docket' }] }),
    )
    expect(toastAddMock).toHaveBeenCalledWith(expect.objectContaining({ severity: 'success', summary: 'ORD-9' }))
    expect(result.printingDocketId.value).toBeNull()
  })

  it('shows the reason of a failed print, such as a disabled printer', async () => {
    printDocumentsMock.mockResolvedValue([{ status: 'failed', error_message: 'Printer #2 is disabled.' }])
    const { result } = mountComposable()

    await result.printOrderDocket(makeOrderResponse({ order_number: 'ORD-3' }))

    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'error', summary: 'ORD-3', detail: 'Printer #2 is disabled.' }),
    )
  })
})
