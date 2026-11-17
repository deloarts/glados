import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { defineComponent, h } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'

const putMock = vi.fn<(url: string, payload?: unknown) => Promise<unknown>>()
const postMock = vi.fn<(url: string, payload?: unknown) => Promise<unknown>>()
// Answers nothing by default; a test that confirms sets an implementation.
const requireMock = vi.fn<
  (options: { message?: string; accept?: () => void; reject?: () => void }) => void
>()

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: { items: [], total: 0 } }),
    put: (url: string, payload?: unknown) => putMock(url, payload),
    post: (url: string, payload?: unknown) => postMock(url, payload),
  },
}))

vi.mock('openvue/useconfirm', () => ({
  useConfirm: () => ({ require: requireMock }),
}))

import LotMaterialSourceDialog from '../LotMaterialSourceDialog.vue'

// The source picker resolves straight away, so Save goes on to the switch.
const MaterialSourceSelectStub = defineComponent({
  name: 'MaterialSourceSelect',
  setup(_, { expose }) {
    expose({ resolve: () => Promise.resolve(true), submitLabel: 'Switch Source' })
    return () => h('div')
  },
})

function mountDialog(props: Record<string, unknown> = {}) {
  return mountWithApp(LotMaterialSourceDialog, {
    attachTo: document.body,
    props: {
      visible: true,
      lotId: 3,
      madeItemId: null,
      currentSource: { bought_item_id: null, source_item_id: 4, made_item_id: null },
      currentDemandStatus: null,
      ...props,
    },
    global: { stubs: { MaterialSourceSelect: MaterialSourceSelectStub } },
  })
}

function saveButton(): HTMLButtonElement {
  const button = Array.from(document.body.querySelectorAll('button')).find((b) =>
    b.textContent?.includes('Switch Source'),
  )
  expect(button).toBeDefined()
  return button as HTMLButtonElement
}

describe('LotMaterialSourceDialog', () => {
  beforeEach(() => {
    putMock.mockReset()
    postMock.mockReset()
    requireMock.mockReset()
  })

  it('shows what arrived before it replaces an ordered demand, then sends the confirm and the edit version', async () => {
    postMock.mockResolvedValue({
      data: {
        5: {
          demand_item_id: 5,
          unit: 'pcs',
          total: 10,
          allocated: 10,
          ordered: 10,
          delivered: 3,
          fulfilled_from_stock: 1,
        },
      },
    })
    putMock.mockResolvedValue({ data: { id: 3 } })
    requireMock.mockImplementation((options) => options.accept?.())
    const wrapper = mountDialog({ currentDemandStatus: 'ordered', inputDemandId: 5, editVersion: 4 })
    await flushPromises()

    saveButton().click()
    await flushPromises()

    const message = requireMock.mock.calls[0]![0].message ?? ''
    expect(message).toContain('4 pcs have arrived')
    expect(message).toContain('missing 6 pcs')
    expect(putMock).toHaveBeenCalledWith(
      '/production-lots/3/material-source',
      expect.objectContaining({ confirm_replace_demand: true, expected_edit_version: 4 }),
    )

    wrapper.unmount()
  })

  it('switches nothing when the user cancels the ordered-demand question', async () => {
    postMock.mockResolvedValue({
      data: {
        5: { demand_item_id: 5, unit: 'pcs', total: 10, allocated: 10, ordered: 10, delivered: 0, fulfilled_from_stock: 0 },
      },
    })
    requireMock.mockImplementation((options) => options.reject?.())
    const wrapper = mountDialog({ currentDemandStatus: 'allocated', inputDemandId: 5, editVersion: 4 })
    await flushPromises()

    saveButton().click()
    await flushPromises()

    expect(requireMock).toHaveBeenCalledOnce()
    expect(putMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('stays open with the server reason and asks the view to reload the lot after a 409', async () => {
    putMock.mockRejectedValueOnce({
      isAxiosError: true,
      response: { status: 409, data: { detail: 'The lot was changed by someone else.' } },
    })
    const wrapper = mountDialog()
    await flushPromises()

    saveButton().click()
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith('/production-lots/3/material-source', expect.anything())
    expect(wrapper.emitted('conflict')).toHaveLength(1)
    expect(wrapper.emitted('updated')).toBeFalsy()
    expect(document.body.textContent).toContain('The lot was changed by someone else.')

    wrapper.unmount()
  })

  it('asks for no reload after another error', async () => {
    putMock.mockRejectedValueOnce({
      isAxiosError: true,
      response: { status: 422, data: { detail: 'Pick a source.' } },
    })
    const wrapper = mountDialog()
    await flushPromises()

    saveButton().click()
    await flushPromises()

    expect(putMock).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('conflict')).toBeFalsy()

    wrapper.unmount()
  })
})
