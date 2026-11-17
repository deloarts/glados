import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import type { ConfirmationOptions } from 'openvue/confirmationoptions'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { usePrintTemplatesStore } from '../../stores/printTemplatesStore'
import { makeDocketTemplate, makeLabelTemplate, signInSystemUser } from './fixtures'

import type { PrintTemplateKind } from '../../utils/printTemplateKinds'
import type { PrintTemplateUpdateRequest } from '../../types/printTemplateRequest'
import type { PrintTemplateResponse } from '../../types/printTemplateResponse'

const updatePrintTemplateMock =
  vi.fn<(classifier: string, payload: PrintTemplateUpdateRequest) => Promise<PrintTemplateResponse>>()
vi.mock('../../api/updatePrintTemplate', () => ({
  updatePrintTemplate: (classifier: string, payload: PrintTemplateUpdateRequest) =>
    updatePrintTemplateMock(classifier, payload),
}))

const disableAllPrintersMock = vi.fn<() => Promise<number>>()
vi.mock('@/features/printers', () => ({
  disableAllPrinters: () => disableAllPrintersMock(),
}))

const confirmRequireMock = vi.fn<(options: ConfirmationOptions) => void>()
vi.mock('openvue/useconfirm', () => ({
  useConfirm: () => ({ require: confirmRequireMock }),
}))

import PrintTemplateManagementControls from '../PrintTemplateManagementControls.vue'

const armedLabel = makeLabelTemplate({ auto_print: true })
const idleLabel = makeLabelTemplate({ id: 2, classifier: 'lot_label', auto_print: false })
const armedDocket = makeDocketTemplate({ auto_print: true })

function mountControls(kind: PrintTemplateKind) {
  const pinia = createPinia()
  setActivePinia(pinia)
  signInSystemUser()
  usePrintTemplatesStore().items = [armedLabel, idleLabel, armedDocket]

  return mountWithApp(PrintTemplateManagementControls, { pinia, props: { kind } })
}

function clickButton(wrapper: ReturnType<typeof mountControls>, icon: string) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('icon') === icon)!
    .trigger('click')
}

function lastConfirm(): ConfirmationOptions {
  return confirmRequireMock.mock.calls.at(-1)![0]
}

describe('PrintTemplateManagementControls', () => {
  beforeEach(() => {
    updatePrintTemplateMock.mockReset()
    disableAllPrintersMock.mockReset()
    confirmRequireMock.mockReset()
  })

  it.each([
    ['label', armedLabel, 'Turn off auto-print for every label template? Manual printing is unaffected.'],
    ['docket', armedDocket, 'Turn off auto-print for every docket template? Manual printing is unaffected.'],
  ] as const)(
    'turns off auto-print only on the armed templates of the %s kind',
    async (kind, armed, message) => {
      updatePrintTemplateMock.mockImplementation(async (classifier, payload) => ({
        ...armed,
        classifier,
        ...payload,
      }) as PrintTemplateResponse)
      const wrapper = mountControls(kind)

      await clickButton(wrapper, 'mdi mdi-flash-off')
      expect(lastConfirm().message).toBe(message)

      await lastConfirm().accept!()
      await flushPromises()

      expect(updatePrintTemplateMock).toHaveBeenCalledTimes(1)
      expect(updatePrintTemplateMock).toHaveBeenCalledWith(armed.classifier, { auto_print: false })

      wrapper.unmount()
    },
  )

  it.each(['label', 'docket'] as const)(
    'disables every printer after confirming on the %s page',
    async (kind) => {
      disableAllPrintersMock.mockResolvedValue(3)
      const wrapper = mountControls(kind)

      await clickButton(wrapper, 'mdi mdi-printer-off')
      expect(lastConfirm().header).toBe('Disable All Printers')

      await lastConfirm().accept!()
      await flushPromises()

      expect(disableAllPrintersMock).toHaveBeenCalledTimes(1)

      wrapper.unmount()
    },
  )
})
