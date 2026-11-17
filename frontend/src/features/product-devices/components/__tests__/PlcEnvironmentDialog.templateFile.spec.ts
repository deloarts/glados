import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { stubFilePicker, textFile } from '@/test-utils/filePicker'
import { serializeTemplateFile } from '@/shared/utils/templateFile'
import type { PlcEnvironment, PlcEnvironmentSaveRequest } from '../../types/productDevice'

const createMock = vi.fn<(body: PlcEnvironmentSaveRequest) => Promise<PlcEnvironment>>()
vi.mock('../../api/plcEnvironmentsApi', () => ({
  createPlcEnvironment: (body: PlcEnvironmentSaveRequest) => createMock(body),
  updatePlcEnvironment: vi.fn<() => Promise<void>>(),
  getPlcEnvironments: () => Promise.resolve([]),
}))

import PlcEnvironmentDialog from '../PlcEnvironmentDialog.vue'

const SHIPPED = readFileSync(resolve(process.cwd(), '../templates/plc-environments/siemens_tia_portal.json'), 'utf8')

function body(selector: string): DOMWrapper<Element> {
  return new DOMWrapper(document.body.querySelector(selector)!)
}

async function mountDialog() {
  setActivePinia(createPinia())
  const wrapper = mountWithApp(PlcEnvironmentDialog, { attachTo: document.body, props: { visible: false } })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

afterEach(() => {
  createMock.mockReset()
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

describe('PlcEnvironmentDialog template files', () => {
  it('fills a new environment from the shipped Siemens TIA Portal file', async () => {
    createMock.mockImplementation(async (b) => ({ ...b, id: 1 }) as unknown as PlcEnvironment)
    const wrapper = await mountDialog()
    stubFilePicker([textFile('siemens_tia_portal.json', SHIPPED)])

    await body('[data-testid="plc-import"]').trigger('click')
    await flushPromises()
    await body('form.plc-form').trigger('submit')
    await flushPromises()

    const { glados_template: _kind, version: _version, ...expected } = JSON.parse(SHIPPED) as Record<string, unknown>
    expect(createMock).toHaveBeenCalledWith({ ...expected, is_default: false })
    wrapper.unmount()
  })

  it('leaves the form as it was for a file of another kind', async () => {
    const wrapper = await mountDialog()
    stubFilePicker([textFile('variable_maps.json', serializeTemplateFile('pdm_variable_maps', {}))])

    await body('[data-testid="plc-import"]').trigger('click')
    await flushPromises()

    expect((document.body.querySelector('#plc-name') as HTMLInputElement).value).toBe('')
    expect(document.body.querySelectorAll('[data-testid="plc-column"]')).toHaveLength(0)
    wrapper.unmount()
  })
})
