import { describe, it, expect } from 'vitest'
import { ref } from 'vue'

import { useDemandUnitOptions } from '../useDemandUnitOptions'

describe('useDemandUnitOptions', () => {
  it('maps each unit code to a value/label option in order', () => {
    const options = useDemandUnitOptions(['PCS', 'KG'], (code) => `label:${code}`)

    expect(options.value).toEqual([
      { value: 'PCS', label: 'label:PCS' },
      { value: 'KG', label: 'label:KG' },
    ])
  })

  it('stays reactive to a label function that reads reactive state, like vue-i18n t()', () => {
    const locale = ref('en')
    const options = useDemandUnitOptions(['PCS'], (code) => `${code}-${locale.value}`)

    expect(options.value).toEqual([{ value: 'PCS', label: 'PCS-en' }])

    locale.value = 'de'
    expect(options.value).toEqual([{ value: 'PCS', label: 'PCS-de' }])
  })
})
