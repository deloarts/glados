import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import type { ConfirmationOptions } from 'openvue/confirmationoptions'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { usePrintTemplatesStore } from '../../stores/printTemplatesStore'
import { makeDocketTemplate, makeLabelTemplate, signInSystemUser } from './fixtures'

import type { PrintTemplateKind } from '../../utils/printTemplateKinds'
import type { PrintTemplateResponse } from '../../types/printTemplateResponse'

// The date cells load the user list for the actor's card; it stays empty
// here so the request never reaches the network.
vi.mock('@/core/api/users/getUserDirectory', () => ({
  getUserDirectory: async () => ({ items: [], total: 0, limit: 0, skip: 0 }),
}))

const getPrintTemplatesMock = vi.fn<() => Promise<PrintTemplateResponse[]>>()
vi.mock('../../api/getPrintTemplates', () => ({
  getPrintTemplates: () => getPrintTemplatesMock(),
}))

const confirmRequireMock = vi.fn<(options: ConfirmationOptions) => void>()
vi.mock('openvue/useconfirm', () => ({
  useConfirm: () => ({ require: confirmRequireMock }),
}))

import PrintTemplateManagementTable from '../PrintTemplateManagementTable.vue'

const label = makeLabelTemplate()
const docket = makeDocketTemplate()

async function mountTable(kind: PrintTemplateKind) {
  getPrintTemplatesMock.mockResolvedValue([label, docket])
  const pinia = createPinia()
  setActivePinia(pinia)
  signInSystemUser()

  const wrapper = mountWithApp(PrintTemplateManagementTable, { pinia, props: { kind } })
  await flushPromises()
  return wrapper
}

describe('PrintTemplateManagementTable', () => {
  beforeEach(() => {
    getPrintTemplatesMock.mockReset()
    confirmRequireMock.mockReset()
  })

  it('shows only label rows and no page size column for labels', async () => {
    const wrapper = await mountTable('label')

    expect(wrapper.text()).toContain('Production Order Label')
    expect(wrapper.text()).not.toContain('Lot Docket')
    expect(wrapper.text()).not.toContain('Page Size')

    wrapper.unmount()
  })

  it('shows only docket rows and their page size for dockets', async () => {
    const wrapper = await mountTable('docket')

    expect(wrapper.text()).toContain('Lot Docket')
    expect(wrapper.text()).not.toContain('Production Order Label')
    expect(wrapper.text()).toContain('Page Size')
    expect(wrapper.text()).toContain('A4')

    wrapper.unmount()
  })

  it.each([
    ['label', label, 'Clear "Production Order Label"\'s content? Your changes will be lost.'],
    ['docket', docket, 'Clear "Lot Docket"\'s content? Your changes will be lost.'],
  ] as const)(
    'emits edit and preview and asks before a reset for the %s kind',
    async (kind, template, confirmMessage) => {
      const wrapper = await mountTable(kind)
      usePrintTemplatesStore().showActions = true
      await flushPromises()

      const buttons = wrapper.findAllComponents({ name: 'Button' })
      await buttons.find((b) => b.props('icon') === 'mdi mdi-pencil')!.trigger('click')
      await buttons.find((b) => b.props('icon') === 'mdi mdi-eye-outline')!.trigger('click')
      await buttons.find((b) => b.props('icon') === 'mdi mdi-backup-restore')!.trigger('click')

      expect(wrapper.emitted('edit')).toEqual([[template]])
      expect(wrapper.emitted('preview')).toEqual([[template]])
      expect(confirmRequireMock).toHaveBeenCalledWith(
        expect.objectContaining({ message: confirmMessage }),
      )

      wrapper.unmount()
    },
  )
})
