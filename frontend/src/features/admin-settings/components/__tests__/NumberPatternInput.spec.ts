import { describe, expect, it } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import NumberPatternInput from '../NumberPatternInput.vue'

function mountInput(pattern: string) {
  return mountWithApp(NumberPatternInput, {
    props: { modelValue: pattern, inputId: 'pattern-test' },
  })
}

describe('NumberPatternInput', () => {
  it('warns about a pipe inside square brackets', () => {
    const wrapper = mountInput('[M|V]\\d{5}')
    expect(wrapper.text()).toContain('Inside square brackets | is an ordinary character')
  })

  it('stays quiet for an alternative in parentheses', () => {
    const wrapper = mountInput('(M|V)\\d{5}')
    expect(wrapper.text()).not.toContain('Inside square brackets')
  })

  it('tests a typed sample against the pattern', async () => {
    const wrapper = mountInput('P\\d{3}')
    const inputs = wrapper.findAll('input')
    await inputs[1]!.setValue('P123')
    expect(wrapper.text()).toContain('Matches')
    await inputs[1]!.setValue('X1')
    expect(wrapper.text()).not.toContain('Matches')
  })
})
