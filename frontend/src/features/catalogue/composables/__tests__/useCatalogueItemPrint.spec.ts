import { describe, it, expect, vi, beforeEach } from 'vitest'
import { defineComponent, h } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'

const printDocumentsMock =
  vi.fn<
    (body: unknown) => Promise<{ status: 'sent' | 'failed'; error_message: string | null }[]>
  >()
vi.mock('@/features/print-labels/api/printDocuments', () => ({
  printDocuments: (body: unknown) => printDocumentsMock(body),
}))

const toastAddMock = vi.fn<(message: unknown) => void>()
vi.mock('openvue/usetoast', () => ({
  useToast: () => ({ add: toastAddMock }),
}))

import { useCatalogueItemPrint } from '../useCatalogueItemPrint'

import type { CatalogueItemKind } from '../../types/itemDetail'

function mountComposable(kind: CatalogueItemKind) {
  let result!: ReturnType<typeof useCatalogueItemPrint>
  const wrapper = mountWithApp(
    defineComponent({
      setup() {
        result = useCatalogueItemPrint(kind)
        return () => h('div')
      },
    }),
  )
  return { result, wrapper }
}

describe('useCatalogueItemPrint', () => {
  beforeEach(() => {
    printDocumentsMock.mockReset()
    toastAddMock.mockReset()
  })

  it('starts with nothing printing', () => {
    const { result } = mountComposable('bought')
    expect(result.printing.value).toBeNull()
  })

  it('tracks which target is printing, then clears it', async () => {
    let resolve!: (value: { status: 'sent'; error_message: null }[]) => void
    printDocumentsMock.mockReturnValue(
      new Promise((r) => {
        resolve = r
      }),
    )
    const { result } = mountComposable('bought')

    const promise = result.print({ id: 1, summary: 'Item 1' }, 'label')
    expect(result.printing.value).toBe('label')

    resolve([{ status: 'sent', error_message: null }])
    await promise

    expect(result.printing.value).toBeNull()
  })

  it('sends the root type and classifier for the given kind', async () => {
    printDocumentsMock.mockResolvedValue([{ status: 'sent', error_message: null }])
    const { result } = mountComposable('made')

    await result.print({ id: 7, summary: 'Widget' }, 'docket')

    expect(printDocumentsMock).toHaveBeenCalledWith({
      root_type: 'made_item',
      root_id: 7,
      items: [{ classifier: 'made_item_docket' }],
    })
  })

  it('shows a success toast when the job is sent', async () => {
    printDocumentsMock.mockResolvedValue([{ status: 'sent', error_message: null }])
    const { result } = mountComposable('source')

    await result.print({ id: 3, summary: 'Raw Block' }, 'label')

    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({
        severity: 'success',
        summary: 'Raw Block',
        detail: 'Label sent to printer.',
      }),
    )
  })

  it('shows an error toast with the job error message when the job failed', async () => {
    printDocumentsMock.mockResolvedValue([{ status: 'failed', error_message: 'No printer configured' }])
    const { result } = mountComposable('bought')

    await result.print({ id: 3, summary: 'Bolt' }, 'docket')

    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'error', summary: 'Bolt', detail: 'No printer configured' }),
    )
  })

  it('falls back to the generic failed copy when the job carries no error message', async () => {
    printDocumentsMock.mockResolvedValue([{ status: 'failed', error_message: null }])
    const { result } = mountComposable('bought')

    await result.print({ id: 3, summary: 'Bolt' }, 'label')

    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({ detail: 'Could not print the label.' }),
    )
  })

  it('shows an error toast and clears printing when the request throws', async () => {
    printDocumentsMock.mockRejectedValue(new Error('network error'))
    const { result } = mountComposable('source')

    await result.print({ id: 9, summary: 'Sheet' }, 'docket')

    expect(result.printing.value).toBeNull()
    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({
        severity: 'error',
        summary: 'Sheet',
        detail: 'Could not print the docket.',
      }),
    )
  })
})
