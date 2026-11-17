import { afterEach, describe, expect, it, vi } from 'vitest'
import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { PlcTag } from '../../types/productDevice'

const setNameMock = vi.fn<(...args: unknown[]) => Promise<void>>()
const createMock = vi.fn<(...args: unknown[]) => Promise<void>>()
vi.mock('../../api/plcTagsApi', () => ({
  setSignalTagName: (...args: unknown[]) => setNameMock(...args),
  createManualPlcTag: (...args: unknown[]) => createMock(...args),
  updateManualPlcTag: vi.fn<() => Promise<void>>(),
}))

import PlcTagDialog from '../PlcTagDialog.vue'

const BUILT: PlcTag = {
  device_id: 4,
  device_name: 'B01 Zylinder P1',
  device_name_ascii: 'B01_Zylinder_P1',
  component_id: 40,
  signal_index: 1,
  name: 'di_B01_Zylinder_P1_AUS',
  tag_table: 'T',
  address: null,
  comment: 'B01 Zylinder P1: aus',
  signal_type: 'di',
  safety: false,
  data_type: '',
  overridden: true,
  too_long: false,
  duplicate: false,
  manual_id: null,
}

async function mountDialog(tag?: PlcTag) {
  setActivePinia(createPinia())
  const wrapper = mountWithApp(PlcTagDialog, { attachTo: document.body, props: { productId: 3, tag, visible: false } })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

function body(selector: string): DOMWrapper<Element> {
  return new DOMWrapper(document.body.querySelector(selector)!)
}

afterEach(() => {
  setNameMock.mockReset()
  createMock.mockReset()
  document.body.innerHTML = ''
})

describe('PlcTagDialog', () => {
  it('stores a new name of a built tag on its signal, and resets it', async () => {
    setNameMock.mockResolvedValue()
    const wrapper = await mountDialog(BUILT)
    await body('[data-testid="plc-tag-name"]').setValue('diZylAus')
    await body('form.tag-form').trigger('submit')
    await flushPromises()
    expect(setNameMock).toHaveBeenCalledWith(4, 40, 1, 'diZylAus')
    wrapper.unmount()

    const again = await mountDialog(BUILT)
    await body('[data-testid="plc-tag-reset"]').trigger('click')
    await flushPromises()
    expect(setNameMock).toHaveBeenLastCalledWith(4, 40, 1, null)
    again.unmount()
  })

  it('adds a manual tag and refuses a name with spaces', async () => {
    createMock.mockResolvedValue()
    const wrapper = await mountDialog()
    await body('[data-testid="plc-tag-name"]').setValue('dq Hupe')
    await body('form.tag-form').trigger('submit')
    await flushPromises()
    expect(createMock).not.toHaveBeenCalled()

    await body('[data-testid="plc-tag-name"]').setValue('dq_Hupe')
    await body('form.tag-form').trigger('submit')
    await flushPromises()
    expect(createMock).toHaveBeenCalledWith(3, {
      name: 'dq_Hupe',
      signal_type: 'di',
      safety: false,
      address: null,
      comment: '',
    })
    wrapper.unmount()
  })
})
