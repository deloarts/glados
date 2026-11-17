import { describe, it, expect } from 'vitest'
import { h } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'

import WithValue from '../WithValue.vue'

describe('WithValue', () => {
  it('passes the value prop through to the default slot', () => {
    const wrapper = mountWithApp(WithValue<number>, {
      props: { value: 42 },
      slots: {
        default: (props: { value: number }) => h('span', String(props.value)),
      },
    })

    expect(wrapper.text()).toBe('42')

    wrapper.unmount()
  })

  it('adds no wrapping element of its own around the slot content', () => {
    const wrapper = mountWithApp(WithValue<string>, {
      props: { value: 'hello' },
      slots: {
        default: (props: { value: string }) => h('span', { class: 'inner' }, props.value),
      },
    })

    expect(wrapper.html()).toBe('<span class="inner">hello</span>')

    wrapper.unmount()
  })

  it('re-renders the slot when the value prop changes', async () => {
    const wrapper = mountWithApp(WithValue<number>, {
      props: { value: 1 },
      slots: {
        default: (props: { value: number }) => h('span', String(props.value)),
      },
    })

    expect(wrapper.text()).toBe('1')

    await wrapper.setProps({ value: 2 })
    expect(wrapper.text()).toBe('2')

    wrapper.unmount()
  })

  it('only calls a getter passed as the value once per render, not once per slot reference', () => {
    let calls = 0
    function expensiveLookup(): { total: number } {
      calls++
      return { total: 7 }
    }

    const wrapper = mountWithApp(WithValue<{ total: number }>, {
      props: { value: expensiveLookup() },
      slots: {
        default: (props: { value: { total: number } }) =>
          h('span', `${props.value.total}/${props.value.total}`),
      },
    })

    expect(calls).toBe(1)
    expect(wrapper.text()).toBe('7/7')

    wrapper.unmount()
  })
})
