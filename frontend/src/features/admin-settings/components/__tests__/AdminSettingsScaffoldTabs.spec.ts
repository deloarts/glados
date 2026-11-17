import { describe, it, expect } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import OpenVue from 'openvue/config'
import ToastService from 'openvue/toastservice'
import Aura from '@openvue/themes/aura'

import { i18n } from '@/core/i18n'

import AdminSettingsTabAiModels from '../AdminSettingsTabAiModels.vue'

// AI Models is still a scaffold with no settings domain behind it yet:
// these tests pin the section heading the eventual fields will slot under,
// and that the layout-parity Save button cannot be clicked into a no-op
// save. The SolidWorks PDM and the stock service tabs stopped being
// scaffolds once they got real content; see their own specs.

async function mountTab(component: typeof AdminSettingsTabAiModels) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mount(component, {
    global: {
      plugins: [pinia, [OpenVue, { theme: { preset: Aura } }], ToastService, i18n],
    },
  })
  await flushPromises()
  return wrapper
}

function sectionLabels(wrapper: ReturnType<typeof mount>): string[] {
  return wrapper.findAll('.section-label').map((el) => el.text())
}

// Checked on the rendered <button>: OpenVue's Button forwards `disabled`
// to the element rather than declaring it as a prop.
function saveButton(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (i18n.global.t('common.save') as string))!
}

describe('AdminSettingsTabAiModels (scaffold)', () => {
  it('renders the Production Time Estimation section', async () => {
    const wrapper = await mountTab(AdminSettingsTabAiModels)

    expect(sectionLabels(wrapper)).toEqual([
      i18n.global.t('adminSettings.aiModels.productionTimeEstimationSection'),
    ])

    wrapper.unmount()
  })

  it('keeps the Save button disabled while there is nothing to save', async () => {
    const wrapper = await mountTab(AdminSettingsTabAiModels)

    expect(saveButton(wrapper).element.hasAttribute('disabled')).toBe(true)

    wrapper.unmount()
  })
})
