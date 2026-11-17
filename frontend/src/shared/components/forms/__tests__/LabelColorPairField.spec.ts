import { describe, it, expect, afterEach } from 'vitest'
import { mountWithApp } from '@/test-utils/mountWithApp'

import { i18n } from '@/core/i18n'
import LabelColorPairField from '../LabelColorPairField.vue'

const baseProps = {
  color: '#6366f1',
  fontColor: '#ffffff',
  colorId: 'lc-color',
  fontColorId: 'lc-font-color',
  colorLabel: 'Label colour',
  fontColorLabel: 'Font colour',
  previewLabel: 'Preview',
  previewText: 'Milling',
}

describe('LabelColorPairField', () => {
  afterEach(() => {
    i18n.global.locale.value = 'enGB'
  })

  it('renders both colour inputs with the given ids and labels', () => {
    const wrapper = mountWithApp(LabelColorPairField, { props: baseProps })

    const colorInput = wrapper.get('#lc-color')
    const fontColorInput = wrapper.get('#lc-font-color')
    expect(colorInput.attributes('type')).toBe('color')
    expect(fontColorInput.attributes('type')).toBe('color')
    expect(wrapper.find('label[for="lc-color"]').text()).toBe('Label colour')
    expect(wrapper.find('label[for="lc-font-color"]').text()).toBe('Font colour')
  })

  it('renders the preview tag with the preview text and the two colours', () => {
    const wrapper = mountWithApp(LabelColorPairField, { props: baseProps })

    const tag = wrapper.get('.preview-tag')
    expect(tag.text()).toBe('Milling')
    expect(tag.attributes('style')).toContain('background: rgb(99, 102, 241)')
    expect(tag.attributes('style')).toContain('color: rgb(255, 255, 255)')
  })

  it('emits update:color when the colour picker input changes', async () => {
    const wrapper = mountWithApp(LabelColorPairField, { props: baseProps })

    const input = wrapper.get('#lc-color')
    await input.setValue('#00ff00')

    expect(wrapper.emitted('update:color')).toEqual([['#00ff00']])
  })

  it('emits update:fontColor when the font-colour picker input changes', async () => {
    const wrapper = mountWithApp(LabelColorPairField, { props: baseProps })

    const input = wrapper.get('#lc-font-color')
    await input.setValue('#000000')

    expect(wrapper.emitted('update:fontColor')).toEqual([['#000000']])
  })

  it('does not show a contrast ratio or warning by default', () => {
    const wrapper = mountWithApp(LabelColorPairField, {
      props: { ...baseProps, color: '#ffff00', fontColor: '#ffffff' },
    })

    expect(wrapper.find('.contrast-ratio').exists()).toBe(false)
    expect(wrapper.find('.contrast-warning').exists()).toBe(false)
  })

  it('shows the contrast ratio when showContrastWarning is on', () => {
    const wrapper = mountWithApp(LabelColorPairField, {
      props: { ...baseProps, showContrastWarning: true },
    })

    expect(wrapper.find('.contrast-ratio').exists()).toBe(true)
  })

  // The badge shows the APCA lightness contrast as a whole number, formatted
  // through the locale like every other number in Glados.
  it('renders the contrast as a whole APCA Lc value', () => {
    i18n.global.locale.value = 'deAT'
    const wrapper = mountWithApp(LabelColorPairField, {
      props: { ...baseProps, color: '#000000', fontColor: '#ffffff', showContrastWarning: true },
    })

    expect(wrapper.get('.contrast-ratio').text()).toBe('Lc 108')
  })

  it('shows the warning message only when the pair is below the WCAG AA threshold', () => {
    const readable = mountWithApp(LabelColorPairField, {
      props: { ...baseProps, color: '#000000', fontColor: '#ffffff', showContrastWarning: true },
    })
    const unreadable = mountWithApp(LabelColorPairField, {
      props: {
        ...baseProps,
        color: '#ffff00',
        fontColor: '#ffffff',
        showContrastWarning: true,
        contrastWarningText: 'Hard to read',
        contrastFixLabel: 'Fix it',
      },
    })

    expect(readable.find('.contrast-warning').exists()).toBe(false)
    expect(unreadable.find('.contrast-warning').exists()).toBe(true)
    expect(unreadable.get('.contrast-warning').text()).toContain('Hard to read')
  })

  it('the fix button emits update:fontColor with a readable colour', async () => {
    const wrapper = mountWithApp(LabelColorPairField, {
      props: {
        ...baseProps,
        color: '#ffff00',
        fontColor: '#ffffff',
        showContrastWarning: true,
        contrastFixLabel: 'Fix it',
      },
    })

    await wrapper.get('.contrast-warning button').trigger('click')

    expect(wrapper.emitted('update:fontColor')).toEqual([['#000000']])
  })
})
