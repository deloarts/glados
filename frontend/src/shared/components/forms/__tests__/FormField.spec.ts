import { describe, it, expect } from 'vitest'
import { mountWithApp } from '@/test-utils/mountWithApp'

import FormField from '../FormField.vue'

describe('FormField', () => {
  it('renders a label whose for matches the id given to the control slot', () => {
    const wrapper = mountWithApp(FormField, {
      props: { label: 'Supplier' },
      slots: {
        default: '<template #default="{ id }"><input :id="id" /></template>',
      },
    })

    const label = wrapper.get('label')
    const input = wrapper.get('input')
    expect(label.attributes('for')).toBe(input.attributes('id'))
    expect(label.attributes('for')).toBeTruthy()
    expect(label.text()).toBe('Supplier')
  })

  it('exposes id and inputId as the same value, for OpenVue controls that take inputId', () => {
    const wrapper = mountWithApp(FormField, {
      props: { label: 'Unit' },
      slots: {
        default:
          '<template #default="{ id, inputId }"><span class="id">{{ id }}</span><span class="input-id">{{ inputId }}</span></template>',
      },
    })

    expect(wrapper.get('.id').text()).toBe(wrapper.get('.input-id').text())
    expect(wrapper.get('.id').text()).toBeTruthy()
  })

  it('gives every instance a distinct id', () => {
    const wrapper = mountWithApp({
      components: { FormField },
      template: `
        <div>
          <FormField label="A"><template #default="{ id }"><span class="a">{{ id }}</span></template></FormField>
          <FormField label="B"><template #default="{ id }"><span class="b">{{ id }}</span></template></FormField>
        </div>
      `,
    })

    expect(wrapper.get('.a').text()).not.toBe(wrapper.get('.b').text())
  })

  it('marks required fields with an aria-hidden asterisk and exposes ariaRequired="true"', () => {
    const wrapper = mountWithApp(FormField, {
      props: { label: 'Quantity', required: true },
      slots: {
        default:
          '<template #default="{ id, ariaRequired }"><input :id="id" :aria-required="ariaRequired" /></template>',
      },
    })

    const marker = wrapper.get('label span')
    expect(marker.attributes('aria-hidden')).toBe('true')
    expect(marker.text()).toBe('*')
    expect(wrapper.get('label').text()).toBe('Quantity *')
    expect(wrapper.get('input').attributes('aria-required')).toBe('true')
  })

  it('renders no marker and no ariaRequired for a field that is not required', () => {
    const wrapper = mountWithApp(FormField, {
      props: { label: 'Note' },
      slots: {
        default:
          '<template #default="{ id, ariaRequired }"><input :id="id" :aria-required="ariaRequired" /></template>',
      },
    })

    expect(wrapper.find('label span').exists()).toBe(false)
    expect(wrapper.get('label').text()).toBe('Note')
    expect(wrapper.get('input').attributes('aria-required')).toBeUndefined()
  })
})
