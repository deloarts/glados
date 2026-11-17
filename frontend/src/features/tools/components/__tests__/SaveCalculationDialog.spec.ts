import { describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'

vi.mock('@/core/api/projects/searchProjects', () => ({
  searchProjects: vi.fn<() => Promise<{ items: never[]; total: number; limit: number; skip: number }>>(
    async () => ({ items: [], total: 0, limit: 50, skip: 0 }),
  ),
}))

import SaveCalculationDialog from '../SaveCalculationDialog.vue'

async function mountDialog() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(SaveCalculationDialog, {
    pinia,
    props: {
      mode: 'create',
      visible: false,
      initial: { owner: { kind: 'personal' }, title: 'Ø25 H7/g6', note: null, deviceId: null },
    },
    attachTo: document.body,
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

function byTestId(id: string): HTMLElement {
  const el = document.querySelector<HTMLElement>(`[data-testid="${id}"]`)
  if (!el) throw new Error(`missing ${id}`)
  return el
}

describe('SaveCalculationDialog', () => {
  it('saves a personal calculation with the proposed title', async () => {
    const wrapper = await mountDialog()

    byTestId('calc-save-submit').click()
    await flushPromises()

    expect(wrapper.emitted('save')?.[0]).toEqual([
      { owner: { kind: 'personal' }, title: 'Ø25 H7/g6', note: null, deviceId: null },
    ])
    wrapper.unmount()
  })

  it('requires a title', async () => {
    const wrapper = await mountDialog()
    const input = byTestId('calc-title') as HTMLInputElement
    input.value = '  '
    input.dispatchEvent(new Event('input'))
    await flushPromises()

    byTestId('calc-save-submit').click()
    await flushPromises()

    expect(wrapper.emitted('save')).toBeUndefined()
    expect(document.body.textContent).toContain('Enter a title.')
    wrapper.unmount()
  })
})
