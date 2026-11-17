import { afterEach, describe, expect, it, vi } from 'vitest'
import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { PlcEnvironment, PlcEnvironmentSaveRequest, PlcEnvironmentSettings } from '../../types/productDevice'

const createMock = vi.fn<(body: PlcEnvironmentSaveRequest) => Promise<PlcEnvironment>>()
vi.mock('../../api/plcEnvironmentsApi', () => ({
  createPlcEnvironment: (body: PlcEnvironmentSaveRequest) => createMock(body),
  updatePlcEnvironment: vi.fn<() => Promise<void>>(),
  getPlcEnvironments: () => Promise.resolve([]),
}))

import PlcEnvironmentDialog from '../PlcEnvironmentDialog.vue'

const TEMPLATE: PlcEnvironmentSettings = {
  name: 'Siemens TIA Portal',
  prefixes: { di: 'di_', do: 'dq_', ai: 'ai_', ao: 'aq_', bus: '', safety_di: 'fdi_', safety_do: 'fdq_', safety_ai: 'fai_', safety_ao: 'faq_' },
  max_tag_length: 128,
  conversions: [{ source: '-', target: '_' }],
  tag_table: 'Standard-Variablentabelle',
  safety_tag_table: null,
  export_sheet: 'PLC Tags',
  export_columns: [{ header: 'Name', source: 'tag_name', value: null }],
}

function body(selector: string): DOMWrapper<Element> {
  return new DOMWrapper(document.body.querySelector(selector)!)
}

async function mountDialog() {
  setActivePinia(createPinia())
  const wrapper = mountWithApp(PlcEnvironmentDialog, {
    attachTo: document.body,
    props: { template: TEMPLATE, visible: false },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

afterEach(() => {
  createMock.mockReset()
  document.body.innerHTML = ''
})

describe('PlcEnvironmentDialog', () => {
  it('starts a new environment from the template and saves it', async () => {
    createMock.mockImplementation(async (b) => ({ ...TEMPLATE, ...b, id: 1, public_id: 'p', created: '', changed: '', archived: false }) as PlcEnvironment)
    const wrapper = await mountDialog()
    expect((document.body.querySelector('#plc-name') as HTMLInputElement).value).toBe('')
    expect((document.body.querySelector('[data-testid="plc-prefix-do"]') as HTMLInputElement).value).toBe('dq_')

    await body('#plc-name').setValue('TIA V19')
    await body('[data-testid="plc-prefix-di"]').setValue('I_')
    await body('form.plc-form').trigger('submit')
    await flushPromises()

    const sent = createMock.mock.calls[0]![0]
    expect(sent.name).toBe('TIA V19')
    expect(sent.prefixes.di).toBe('I_')
    expect(sent.conversions).toEqual([{ source: '-', target: '_' }])
    expect(sent.export_columns).toEqual([{ header: 'Name', source: 'tag_name', value: null }])
    wrapper.unmount()
  })

  it('refuses a conversion without a character', async () => {
    const wrapper = await mountDialog()
    await body('#plc-name').setValue('TIA')
    await body('[data-testid="plc-add-conversion"]').trigger('click')
    await body('form.plc-form').trigger('submit')
    await flushPromises()
    expect(createMock).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('Every conversion needs a character.')
    wrapper.unmount()
  })
})
