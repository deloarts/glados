import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'

import DemandStatusTag from '../DemandStatusTag.vue'

describe('DemandStatusTag', () => {
  it('renders the label passed in', () => {
    const wrapper = mountWithApp(DemandStatusTag, {
      props: { label: 'Fulfilled', severity: 'success' },
    })

    expect(wrapper.text()).toBe('Fulfilled')
  })

  it('passes the severity through to the underlying Tag', () => {
    const wrapper = mountWithApp(DemandStatusTag, {
      props: { label: 'Open', severity: 'warn' },
    })

    expect(wrapper.findComponent({ name: 'Tag' }).props('severity')).toBe('warn')
  })
})
