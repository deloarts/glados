import { describe, expect, it } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import SectionCard from '../SectionCard.vue'

describe('SectionCard', () => {
  it('renders the title, hint, icon and title-end slot inside the card', () => {
    const wrapper = mountWithApp(SectionCard, {
      props: { title: 'Sessions', hint: 'Every device you are signed in on.', icon: 'mdi-laptop' },
      slots: { default: '<p class="content">Body</p>', 'title-end': '<span class="count">3</span>' },
    })

    const header = wrapper.find('.card .section-card-header')
    expect(header.find('.section-card-title').text()).toBe('Sessions')
    expect(header.find('.section-card-hint').text()).toBe('Every device you are signed in on.')
    expect(header.find('.section-card-icon').classes()).toContain('mdi-laptop')
    expect(header.find('.count').text()).toBe('3')
    expect(wrapper.find('.section-card-body .content').text()).toBe('Body')
  })

  it('leaves out the hint and icon when none is given', () => {
    const wrapper = mountWithApp(SectionCard, { props: { title: 'Sessions' } })

    expect(wrapper.find('.section-card-hint').exists()).toBe(false)
    expect(wrapper.find('.section-card-icon').exists()).toBe(false)
  })

  it('marks the card flush and fill when asked', () => {
    const wrapper = mountWithApp(SectionCard, { props: { title: 'Sessions', flush: true, fill: true } })

    expect(wrapper.classes()).toEqual(expect.arrayContaining(['flush', 'fill']))
  })
})
