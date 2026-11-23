import { describe, expect, it } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import AutoComplete from 'openvue/autocomplete'

import { mountWithApp } from '@/test-utils/mountWithApp'

import TextChipsInput from '../TextChipsInput.vue'
import { normaliseChips } from '../textChips'

describe('normaliseChips', () => {
  it('trims the values and drops empty ones', () => {
    expect(normaliseChips([' AB-1 ', '', '   ', 'AB-2'])).toEqual(['AB-1', 'AB-2'])
  })

  it('keeps the first spelling of a value repeated in another case, in entry order', () => {
    expect(normaliseChips(['ab-1', 'Müller-7', 'AB-1', 'müller-7'])).toEqual(['ab-1', 'Müller-7'])
  })
})

describe('TextChipsInput', () => {
  async function mountInput(modelValue: string[]) {
    const wrapper = mountWithApp(TextChipsInput, { props: { modelValue } })
    await flushPromises()
    return wrapper
  }

  it('takes the typed text as a chip on a comma and empties the input', async () => {
    const wrapper = await mountInput(['AB-1'])
    const field = wrapper.get('input')

    ;(field.element as HTMLInputElement).value = ' AB-2 '
    await field.trigger('keydown', { key: ',' })

    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([['AB-1', 'AB-2']])
    expect((field.element as HTMLInputElement).value).toBe('')
    wrapper.unmount()
  })

  it('takes the typed text as a chip on Enter', async () => {
    const wrapper = await mountInput([])
    const field = wrapper.get('input')

    ;(field.element as HTMLInputElement).value = 'AB-3'
    await field.trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([['AB-3']])
    wrapper.unmount()
  })

  it('ignores a comma on an empty input', async () => {
    const wrapper = await mountInput(['AB-1'])

    await wrapper.get('input').trigger('keydown', { key: ',' })

    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    wrapper.unmount()
  })

  it('takes typed but unconfirmed text through commitPending', async () => {
    const wrapper = await mountInput(['AB-1'])
    ;(wrapper.get('input').element as HTMLInputElement).value = 'ab-1'

    ;(wrapper.vm as unknown as { commitPending(): void }).commitPending()

    // A repeat in another case is kept once, in its first spelling.
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([['AB-1']])
    wrapper.unmount()
  })

  it('normalises the list the chips leave after one is removed', async () => {
    const wrapper = await mountInput(['AB-1', 'AB-2'])

    wrapper.findComponent(AutoComplete).vm.$emit('update:modelValue', [' AB-2 '])
    await flushPromises()

    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([['AB-2']])
    wrapper.unmount()
  })
})
