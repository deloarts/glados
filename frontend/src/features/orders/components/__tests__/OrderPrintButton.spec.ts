import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeOrderResponse, userWithPermissions } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'

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

import OrderPrintButton from '../OrderPrintButton.vue'

function mountButton(permissions: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  return mountWithApp(OrderPrintButton, {
    props: { order: makeOrderResponse({ id: 42 }) },
    pinia,
    attachTo: document.body,
    global: { directives: { tooltip: Tooltip } },
  })
}

// The menu is a popup, so its entries render outside the component.
async function pick(wrapper: ReturnType<typeof mountButton>, entry: 'download' | 'print') {
  await wrapper.get('[data-testid="order-print"]').trigger('click')
  await flushPromises()
  const item = document.body.querySelector(`[data-testid="order-docket-${entry}"]`)
  expect(item).toBeTruthy()
  item!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  await flushPromises()
}

describe('OrderPrintButton', () => {
  beforeEach(() => {
    downloadPrintTemplateMock.mockReset().mockResolvedValue({ warnings: [] })
    printDocumentsMock.mockReset().mockResolvedValue([{ status: 'sent', error_message: null }])
  })

  it('downloads the order docket from its menu', async () => {
    const wrapper = mountButton(['print:documents'])

    await pick(wrapper, 'download')

    expect(downloadPrintTemplateMock).toHaveBeenCalledWith('order_docket', 'order', 42)
    wrapper.unmount()
  })

  it('sends the order docket to its printer from its menu', async () => {
    const wrapper = mountButton(['print:documents'])

    await pick(wrapper, 'print')

    expect(printDocumentsMock).toHaveBeenCalledWith({
      root_type: 'order',
      root_id: 42,
      items: [{ classifier: 'order_docket' }],
    })
    wrapper.unmount()
  })

  it('is disabled without the permission to print documents', () => {
    const wrapper = mountButton([])

    expect(wrapper.get('[data-testid="order-print"]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })
})
