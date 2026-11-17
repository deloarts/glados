import { describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useHostStore } from '@/core/host/stores/hostStore'
import { mountWithApp } from '@/test-utils/mountWithApp'
import LocalizedTextInput from '../LocalizedTextInput.vue'

function mountInput(modelValue: Record<string, string>, required = true, compact = false) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const host = useHostStore()
  host.languages = ['enGB', 'deAT']
  host.defaultLanguage = 'deAT'
  return mountWithApp(LocalizedTextInput, {
    pinia,
    props: { label: 'Label', required, modelValue, compact },
  })
}

describe('LocalizedTextInput', () => {
  it('renders one input per language with the default language first', () => {
    const wrapper = mountInput({ enGB: 'Open' })
    const inputs = wrapper.findAll('input')
    expect(inputs).toHaveLength(2)
    expect(inputs[0]!.attributes('data-testid')).toBe('localized-text-deAT')
    expect((inputs[1]!.element as HTMLInputElement).value).toBe('Open')
  })

  it('marks only the default language as required', () => {
    const wrapper = mountInput({})
    expect(wrapper.get('[data-testid="localized-text-deAT"]').attributes('aria-required')).toBe(
      'true',
    )
    expect(
      wrapper.get('[data-testid="localized-text-enGB"]').attributes('aria-required'),
    ).toBeUndefined()
  })

  it('emits the whole map when one language changes', async () => {
    const wrapper = mountInput({ enGB: 'Open' })
    await wrapper.get('[data-testid="localized-text-deAT"]').setValue('Offen')
    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted?.at(-1)).toEqual([{ enGB: 'Open', deAT: 'Offen' }])
  })

  it('labels each compact input with the label and its language', () => {
    const wrapper = mountInput({}, true, true)
    const input = wrapper.get('[data-testid="localized-text-deAT"]')
    const label = wrapper.get(`label[for="${input.attributes('id')}"]`)
    expect(label.text()).toMatch(/^Label \(.+\) \*$/)
    expect(input.attributes('placeholder')).toBeUndefined()
  })
})
