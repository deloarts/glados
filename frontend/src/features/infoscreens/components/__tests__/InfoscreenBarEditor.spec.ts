import { describe, it, expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import InfoscreenBarEditor from '../InfoscreenBarEditor.vue'

import type { InfoscreenBarState, InfoscreenBarArea } from '../../types/infoscreenResponse'

function makeBar(overrides: Partial<InfoscreenBarState> = {}): InfoscreenBarState {
  return { left: [], center: [], right: [], text: null, ...overrides }
}

function mountBar(bar: InfoscreenBarState, show = true) {
  return mountWithApp(InfoscreenBarEditor, {
    props: { label: 'Show header', idPrefix: 'bar', submitted: false, show, bar },
  })
}

function lastBar(wrapper: ReturnType<typeof mountBar>): InfoscreenBarState {
  const updates = wrapper.emitted('update:bar') as InfoscreenBarState[][]
  return updates[updates.length - 1]![0]!
}

function addSelect(wrapper: ReturnType<typeof mountBar>, area: InfoscreenBarArea) {
  return wrapper
    .findAllComponents({ name: 'Select' })
    .find((select) => select.attributes('data-testid') === `bar-${area}-add`)!
}

function offered(wrapper: ReturnType<typeof mountBar>, area: InfoscreenBarArea): string[] {
  return (addSelect(wrapper, area).props('options') as { value: string }[]).map((o) => o.value)
}

describe('InfoscreenBarEditor', () => {
  it('shows the three areas with their labels and items', async () => {
    const wrapper = mountBar(makeBar({ left: ['logo', 'title'], right: ['clock'] }))
    await flushPromises()

    for (const area of ['left', 'center', 'right'] as const) {
      expect(wrapper.get(`[data-testid="bar-${area}"]`).text()).toContain(
        i18n.global.t(`infoscreens.barAreas.${area}`),
      )
    }
    expect(wrapper.get('[data-testid="bar-left-items"]').text()).toMatch(/Logo.*Screen name/s)
    expect(wrapper.get('[data-testid="bar-right-items"]').text()).toContain('Clock')
  })

  it('offers in every area only the items the bar does not use yet', async () => {
    const wrapper = mountBar(makeBar({ left: ['logo'], center: ['title'], right: ['clock'] }))
    await flushPromises()

    const free = ['app_name', 'company_name', 'date', 'next_holiday', 'last_updated', 'text']
    expect(offered(wrapper, 'left')).toEqual(free)
    expect(offered(wrapper, 'center')).toEqual(free)
    expect(offered(wrapper, 'right')).toEqual(free)
  })

  it('adds an item to the area it was picked in', async () => {
    const wrapper = mountBar(makeBar({ left: ['logo'] }))
    await flushPromises()

    await addSelect(wrapper, 'center').vm.$emit('update:modelValue', 'date')

    expect(lastBar(wrapper)).toEqual(makeBar({ left: ['logo'], center: ['date'] }))
  })

  it('offers the app name and places it like any other item', async () => {
    const wrapper = mountBar(makeBar({ left: ['logo'] }))
    await flushPromises()

    expect(offered(wrapper, 'right')).toContain('app_name')
    await addSelect(wrapper, 'right').vm.$emit('update:modelValue', 'app_name')

    expect(lastBar(wrapper)).toEqual(makeBar({ left: ['logo'], right: ['app_name'] }))
    expect(offered(wrapper, 'center')).not.toContain('app_name')
    expect(wrapper.get('[data-testid="bar-right-items"]').text()).toContain(
      i18n.global.t('infoscreens.barItems.app_name'),
    )
  })

  it('reorders within an area and moves to the neighbouring area', async () => {
    const wrapper = mountBar(makeBar({ left: ['logo', 'title'], right: ['clock'] }))
    await flushPromises()

    await wrapper.get('[data-testid="bar-earlier-title"]').trigger('click')
    expect(lastBar(wrapper)).toEqual(makeBar({ left: ['title', 'logo'], right: ['clock'] }))

    await wrapper.get('[data-testid="bar-right-logo"]').trigger('click')
    expect(lastBar(wrapper)).toEqual(makeBar({ left: ['title'], center: ['logo'], right: ['clock'] }))

    await wrapper.get('[data-testid="bar-left-clock"]').trigger('click')
    expect(lastBar(wrapper)).toEqual(makeBar({ left: ['title'], center: ['logo', 'clock'] }))

    await wrapper.get('[data-testid="bar-remove-title"]').trigger('click')
    expect(lastBar(wrapper)).toEqual(makeBar({ center: ['logo', 'clock'] }))
  })

  it('offers no move beyond the outer areas', async () => {
    const wrapper = mountBar(makeBar({ left: ['logo'], right: ['clock'] }))
    await flushPromises()

    expect(wrapper.find('[data-testid="bar-left-logo"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="bar-right-clock"]').exists()).toBe(false)
  })

  it('shows the text field when the text item sits in any area', async () => {
    const without = mountBar(makeBar({ left: ['logo'] }))
    await flushPromises()
    expect(without.find('[data-testid="bar-text"]').exists()).toBe(false)

    const withText = mountBar(makeBar({ center: ['text'], text: 'Welcome' }))
    await flushPromises()
    await withText.get('[data-testid="bar-text"]').setValue('Hello')
    expect(lastBar(withText)).toEqual(makeBar({ center: ['text'], text: 'Hello' }))
  })

  it('hides the areas while the bar is switched off', async () => {
    const wrapper = mountBar(makeBar({ right: ['last_updated'] }), false)
    await flushPromises()

    expect(wrapper.find('[data-testid="bar-left"]').exists()).toBe(false)
  })
})
