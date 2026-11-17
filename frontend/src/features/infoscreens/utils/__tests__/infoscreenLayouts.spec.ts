import { describe, it, expect } from 'vitest'

import {
  LAYOUTS,
  LAYOUT_SLOT_COUNTS,
  WIDGET_TYPES,
  changeLayout,
  defaultWidget,
  emptyPage,
  isWidgetComplete,
  normaliseWidget,
  defaultFooter,
  defaultHeader,
  BAR_ITEMS,
  barItems,
  isBarComplete,
  toBarState,
  normaliseBar,
  MESSAGE_SEVERITIES,
  MESSAGE_TEXT_ALIGNS,
  MESSAGE_VERTICAL_ALIGNS,
} from '../infoscreenLayouts'

import type { MessageWidgetConfig } from '../../types/infoscreenResponse'

function message(overrides: Partial<MessageWidgetConfig> = {}): MessageWidgetConfig {
  return {
    type: 'message',
    title: null,
    text: '',
    severity: 'info',
    text_align: 'left',
    vertical_align: 'middle',
    ...overrides,
  }
}

describe('infoscreenLayouts', () => {
  it('gives every layout its number of positions', () => {
    expect(LAYOUT_SLOT_COUNTS).toEqual({
      full: 1,
      two_columns: 2,
      main_side: 2,
      grid_2x2: 4,
      two_rows: 2,
      three_rows: 3,
      grid_2x3: 6,
      grid_3x2: 6,
    })
    for (const layout of LAYOUTS) {
      expect(emptyPage(layout).slots).toEqual(Array(LAYOUT_SLOT_COUNTS[layout]).fill(null))
    }
  })

  it('keeps placed widgets in place when the layout grows or shrinks', () => {
    const clock = defaultWidget('clock')
    const message = { ...defaultWidget('message'), text: 'Hello' }
    const grid = changeLayout({ layout: 'two_columns', slots: [clock, message] }, 'grid_2x2')

    expect(grid).toEqual({ layout: 'grid_2x2', slots: [clock, message, null, null] })
    expect(changeLayout(grid, 'full')).toEqual({ layout: 'full', slots: [clock] })
  })

  it('drops the widgets beyond a six slot grid when it shrinks to three rows', () => {
    const widgets = Array.from({ length: 6 }, (_, index) => ({ ...defaultWidget('clock'), title: `C${index}` }))
    const rows = changeLayout({ layout: 'grid_3x2', slots: widgets }, 'three_rows')

    expect(rows).toEqual({ layout: 'three_rows', slots: widgets.slice(0, 3) })
    expect(changeLayout(rows, 'grid_2x3').slots).toEqual([...widgets.slice(0, 3), null, null, null])
  })

  it('starts the header and the footer from the contract defaults', () => {
    expect(defaultHeader()).toEqual({ left: ['logo', 'title'], center: [], right: ['clock'], text: null })
    expect(defaultFooter()).toEqual({ left: [], center: [], right: ['last_updated'], text: null })
  })

  it('sends each bar item once across the areas, the first place wins', () => {
    expect(
      normaliseBar({ left: ['clock', 'logo'], center: ['clock'], right: ['logo', 'date'], text: 'Hi' }),
    ).toEqual({ left: ['clock', 'logo'], center: [], right: ['date'], text: null })
  })

  it('fills the areas the server left out', () => {
    expect(toBarState({ right: ['clock'] })).toEqual({ left: [], center: [], right: ['clock'], text: null })
  })

  it('offers the app name and the company name as bar items', () => {
    expect(BAR_ITEMS).toEqual([
      'logo',
      'app_name',
      'company_name',
      'title',
      'clock',
      'date',
      'next_holiday',
      'last_updated',
      'text',
    ])
  })

  it('keeps the text only while the text item is in some area', () => {
    expect(normaliseBar({ left: [], center: ['text'], right: ['clock'], text: '  Welcome ' })).toEqual({
      left: [],
      center: ['text'],
      right: ['clock'],
      text: 'Welcome',
    })
    expect(barItems({ left: ['logo'], center: ['text'], right: ['clock'], text: null })).toEqual([
      'logo',
      'text',
      'clock',
    ])
    expect(isBarComplete({ left: [], center: [], right: ['text'], text: ' ' })).toBe(false)
    expect(isBarComplete({ left: ['logo'], center: [], right: [], text: null })).toBe(true)
  })

  it('starts every widget type from the contract defaults', () => {
    expect(WIDGET_TYPES.map((type) => defaultWidget(type).type)).toEqual(WIDGET_TYPES)
    expect(defaultWidget('machine_board')).toMatchObject({ machine_ids: [], pool_ids: [], next_count: 3 })
    expect(defaultWidget('lots_due')).toMatchObject({ horizon_days: 7, pool_ids: [], show_customer: false })
    expect(defaultWidget('late_lots')).toMatchObject({ show_customer: false })
    expect(defaultWidget('deliveries_expected')).toMatchObject({ horizon_days: 0 })
    expect(defaultWidget('message')).toMatchObject({
      text: '',
      severity: 'info',
      text_align: 'left',
      vertical_align: 'middle',
    })
    expect(defaultWidget('clock')).toMatchObject({
      show_date: true,
      show_next_holiday: false,
      show_seconds: false,
      style: 'digital',
    })
    for (const type of WIDGET_TYPES) expect(defaultWidget(type).title).toBeNull()
  })

  it('sends a blank title as null and trims a message', () => {
    expect(normaliseWidget({ ...defaultWidget('qa_queue'), title: '  ' })).toEqual({ type: 'qa_queue', title: null })
    expect(normaliseWidget(message({ title: ' News ', text: ' Hi ' }))).toMatchObject({
      title: 'News',
      text: 'Hi',
    })
    expect(normaliseWidget(null)).toBeNull()
  })

  it('offers a plain message without colour first, and every alignment', () => {
    expect(MESSAGE_SEVERITIES).toEqual(['none', 'info', 'success', 'warning', 'danger'])
    expect(MESSAGE_TEXT_ALIGNS).toEqual(['left', 'center', 'right'])
    expect(MESSAGE_VERTICAL_ALIGNS).toEqual(['top', 'middle', 'bottom'])
  })

  it('keeps the alignment of a message when it is sent', () => {
    expect(
      normaliseWidget(message({ text: ' Hi ', text_align: 'right', vertical_align: 'top' })),
    ).toMatchObject({ text: 'Hi', text_align: 'right', vertical_align: 'top' })
  })

  it('needs a text for a message widget only', () => {
    expect(isWidgetComplete(defaultWidget('message'))).toBe(false)
    expect(isWidgetComplete(message({ text: 'Hi' }))).toBe(true)
    expect(isWidgetComplete(defaultWidget('clock'))).toBe(true)
    expect(isWidgetComplete(null)).toBe(true)
  })

  it('needs a place for the weather and a machine for the machine view', () => {
    const weather = defaultWidget('weather')
    expect(isWidgetComplete(weather)).toBe(false)
    expect(
      isWidgetComplete({ ...weather, location_name: 'Zell am See', country_code: 'AT' } as never),
    ).toBe(true)
    const detail = defaultWidget('machine_detail')
    expect(isWidgetComplete(detail)).toBe(false)
    expect(isWidgetComplete({ ...detail, machine_id: 4 } as never)).toBe(true)
    expect(isWidgetComplete(defaultWidget('products'))).toBe(true)
    expect(isWidgetComplete(defaultWidget('projects'))).toBe(true)
  })
})
