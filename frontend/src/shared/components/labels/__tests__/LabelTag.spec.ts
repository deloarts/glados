import { afterEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useHostStore } from '@/core/host/stores/hostStore'
import { i18n } from '@/core/i18n'
import { mountWithApp } from '@/test-utils/mountWithApp'
import LabelTag from '../LabelTag.vue'

const colours = { label_color: '#6366f1', label_font_color: '#ffffff' }

function mountTag(name: Record<string, string> | string, locale: 'enGB' | 'deAT') {
  const pinia = createPinia()
  setActivePinia(pinia)
  useHostStore().defaultLanguage = 'enGB'
  i18n.global.locale.value = locale
  return mountWithApp(LabelTag, { pinia, props: { label: { name, ...colours } } })
}

describe('LabelTag', () => {
  afterEach(() => {
    i18n.global.locale.value = 'enGB'
  })

  it('shows the name in the current UI language', () => {
    const wrapper = mountTag({ enGB: 'Screws', deAT: 'Screws (deAT)' }, 'deAT')
    expect(wrapper.text()).toBe('Screws (deAT)')
  })

  it('falls back to the default language when the UI language has no text', () => {
    const wrapper = mountTag({ enGB: 'Screws' }, 'deAT')
    expect(wrapper.text()).toBe('Screws')
  })

  it('shows a plain string name as it is', () => {
    const wrapper = mountTag('Contactors', 'deAT')
    expect(wrapper.text()).toBe('Contactors')
  })

  it('renders nothing without a label', () => {
    const wrapper = mountWithApp(LabelTag, { props: { label: null } })
    expect(wrapper.text()).toBe('')
  })
})
