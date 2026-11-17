import { describe, it, expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { defaultWidget, emptyPage } from '../../utils/infoscreenLayouts'
import InfoscreenPageEditor from '../InfoscreenPageEditor.vue'

import type { InfoscreenLayout, InfoscreenPage } from '../../types/infoscreenResponse'

function mountPage(page: InfoscreenPage) {
  return mountWithApp(InfoscreenPageEditor, {
    props: {
      page,
      index: 0,
      count: 2,
      machines: [],
      pools: [],
      submitted: false,
      'onUpdate:page': () => {},
    },
  })
}

function lastPage(wrapper: ReturnType<typeof mountPage>): InfoscreenPage {
  const updates = wrapper.emitted('update:page') as InfoscreenPage[][]
  return updates[updates.length - 1]![0]!
}

function selectByTestId(wrapper: ReturnType<typeof mountPage>, testId: string) {
  return wrapper
    .findAllComponents({ name: 'Select' })
    .filter((select) => select.attributes('data-testid') === testId)
}

describe('InfoscreenPageEditor', () => {
  it.each<[InfoscreenLayout, number]>([
    ['full', 1],
    ['two_columns', 2],
    ['grid_2x2', 4],
    ['main_side', 2],
    ['two_rows', 2],
    ['three_rows', 3],
    ['grid_2x3', 6],
    ['grid_3x2', 6],
  ])('draws one slot editor per position of %s', async (layout, count) => {
    const wrapper = mountPage(emptyPage(layout))
    await flushPromises()

    expect(wrapper.findAll('[data-testid="infoscreen-slot"]')).toHaveLength(count)
  })

  it('resizes the slots when the layout changes', async () => {
    const clock = defaultWidget('clock')
    const wrapper = mountPage({ layout: 'full', slots: [clock] })
    await flushPromises()

    await selectByTestId(wrapper, 'infoscreen-page-layout')[0]!.vm.$emit('update:modelValue', 'grid_2x2')

    expect(lastPage(wrapper)).toEqual({ layout: 'grid_2x2', slots: [clock, null, null, null] })
  })

  it('drops the widgets that no longer fit when a grid of six becomes two rows', async () => {
    const widgets = Array.from({ length: 6 }, (_, index) => ({ ...defaultWidget('qa_queue'), title: `Q${index}` }))
    const wrapper = mountPage({ layout: 'grid_3x2', slots: widgets })
    await flushPromises()

    await selectByTestId(wrapper, 'infoscreen-page-layout')[0]!.vm.$emit('update:modelValue', 'two_rows')

    expect(lastPage(wrapper)).toEqual({ layout: 'two_rows', slots: widgets.slice(0, 2) })
  })

  it('puts a widget into one position and leaves the others alone', async () => {
    const wrapper = mountPage(emptyPage('main_side'))
    await flushPromises()

    await selectByTestId(wrapper, 'infoscreen-slot-type')[1]!.vm.$emit('update:modelValue', 'lots_due')

    expect(lastPage(wrapper)).toEqual({ layout: 'main_side', slots: [null, defaultWidget('lots_due')] })
  })

  it('keeps the title when the widget type changes and empties a slot again', async () => {
    const wrapper = mountPage({ layout: 'full', slots: [{ ...defaultWidget('clock'), title: 'Time' }] })
    await flushPromises()

    const type = selectByTestId(wrapper, 'infoscreen-slot-type')[0]!
    await type.vm.$emit('update:modelValue', 'message')
    expect(lastPage(wrapper).slots[0]).toEqual({ ...defaultWidget('message'), title: 'Time' })

    await type.vm.$emit('update:modelValue', 'empty')
    expect(lastPage(wrapper).slots[0]).toBeNull()
  })

  it('edits the settings of a widget in its slot', async () => {
    const wrapper = mountPage({ layout: 'full', slots: [defaultWidget('message')] })
    await flushPromises()

    await wrapper.get('[data-testid="widget-message-text"]').setValue('Fire drill at 10:00')

    expect(lastPage(wrapper).slots[0]).toMatchObject({ type: 'message', text: 'Fire drill at 10:00' })
  })

  it('offers a message without colour and shows a Markdown hint', async () => {
    const wrapper = mountPage({ layout: 'full', slots: [defaultWidget('message')] })
    await flushPromises()

    const severity = selectByTestId(wrapper, 'widget-message-severity')[0]!
    expect((severity.props('options') as { value: string }[]).map((o) => o.value)).toEqual([
      'none',
      'info',
      'success',
      'warning',
      'danger',
    ])
    await severity.vm.$emit('update:modelValue', 'none')
    expect(lastPage(wrapper).slots[0]).toMatchObject({ type: 'message', severity: 'none' })
    expect(wrapper.text()).toContain(i18n.global.t('infoscreens.widgetFields.markdownHint'))
  })

  it('places a message on the three by three position picker, left and middle first', async () => {
    const wrapper = mountPage({ layout: 'full', slots: [defaultWidget('message')] })
    await flushPromises()
    const cell = (vertical: string, horizontal: string) =>
      wrapper.get(`[data-testid="infoscreen-page-0-slot-0-align-${vertical}-${horizontal}"]`)

    expect(wrapper.findAll('[data-testid^="infoscreen-page-0-slot-0-align-"]')).toHaveLength(9)
    expect(cell('middle', 'left').attributes('aria-pressed')).toBe('true')
    expect(cell('top', 'right').attributes('aria-pressed')).toBe('false')

    await cell('bottom', 'center').trigger('click')

    expect(lastPage(wrapper).slots[0]).toMatchObject({
      type: 'message',
      text_align: 'center',
      vertical_align: 'bottom',
    })
  })

  it('edits the style and the seconds of a clock', async () => {
    const wrapper = mountPage({ layout: 'full', slots: [defaultWidget('clock')] })
    await flushPromises()

    const style = selectByTestId(wrapper, 'widget-clock-style')[0]!
    expect((style.props('options') as { value: string }[]).map((o) => o.value)).toEqual([
      'digital',
      'analogue',
      'binary',
    ])
    await style.vm.$emit('update:modelValue', 'binary')
    expect(lastPage(wrapper).slots[0]).toMatchObject({ type: 'clock', style: 'binary' })

    await wrapper
      .findAllComponents({ name: 'Checkbox' })
      .find((c) => c.attributes('data-testid') === 'widget-clock-seconds')!
      .vm.$emit('update:modelValue', true)
    expect(lastPage(wrapper).slots[0]).toMatchObject({ type: 'clock', show_seconds: true })
  })

  it('cannot remove the only page', async () => {
    const wrapper = mountWithApp(InfoscreenPageEditor, {
      props: { page: emptyPage(), index: 0, count: 1, machines: [], pools: [], submitted: false },
    })
    await flushPromises()

    expect(wrapper.get('[data-testid="infoscreen-page-remove"]').attributes('disabled')).toBeDefined()
  })
})
