import { describe, it, expect } from 'vitest'
import { h } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'

import EmptyState from '../EmptyState.vue'

describe('EmptyState', () => {
  it('falls back to the shared default message when none is given', () => {
    const wrapper = mountWithApp(EmptyState)

    expect(wrapper.find('.empty-state-message').text()).toBe('No entries.')
  })

  it('renders a custom message when given', () => {
    const wrapper = mountWithApp(EmptyState, { props: { message: 'No demands found.' } })

    expect(wrapper.find('.empty-state-message').text()).toBe('No demands found.')
  })

  it('renders with role="status" so assistive tech picks up the state', () => {
    const wrapper = mountWithApp(EmptyState)

    expect(wrapper.attributes('role')).toBe('status')
  })

  it('uses a neutral default icon, hidden from assistive tech', () => {
    const wrapper = mountWithApp(EmptyState)

    const icon = wrapper.find('.empty-state-icon')
    expect(icon.attributes('aria-hidden')).toBe('true')
    expect(icon.classes()).toContain('mdi-package-variant-closed')
  })

  it('lets a caller override the icon', () => {
    const wrapper = mountWithApp(EmptyState, { props: { icon: 'mdi mdi-magnify' } })

    expect(wrapper.find('.empty-state-icon').classes()).toContain('mdi-magnify')
  })

  it('renders no actions row when the default slot is empty', () => {
    const wrapper = mountWithApp(EmptyState)

    expect(wrapper.find('.empty-state-actions').exists()).toBe(false)
  })

  it('renders the default slot as actions when given', () => {
    const wrapper = mountWithApp(EmptyState, {
      slots: { default: () => h('button', 'Create') },
    })

    const actions = wrapper.find('.empty-state-actions')
    expect(actions.exists()).toBe(true)
    expect(actions.text()).toBe('Create')
  })
})
