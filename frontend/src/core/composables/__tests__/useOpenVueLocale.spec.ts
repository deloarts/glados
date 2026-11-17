import { describe, it, expect, afterEach } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { usePrimeVue } from 'openvue/config'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { setDisplayDateFormat } from '@/core/utils/dates'
import { useOpenVueLocale } from '../useOpenVueLocale'

import type { PrimeVueLocaleOptions } from '@openvue/core/config'

// The expected German month names come from Intl for de-AT rather than being
// written out, so this spec holds no German text. An app that resolved the
// wrong locale tag (plain de instead of de-AT, say) would still fail.
function deAtMonthName(month: number, style: 'long' | 'short'): string {
  return new Intl.DateTimeFormat('de-AT', { month: style, timeZone: 'UTC' }).format(
    new Date(Date.UTC(2026, month, 1)),
  )
}

function mountComposable() {
  let locale!: PrimeVueLocaleOptions
  const wrapper = mountWithApp(
    defineComponent({
      setup() {
        useOpenVueLocale()
        locale = usePrimeVue().config.locale as PrimeVueLocaleOptions
        return () => h('div')
      },
    }),
  )
  return { locale, wrapper }
}

describe('useOpenVueLocale', () => {
  afterEach(() => {
    i18n.global.locale.value = 'enGB'
    setDisplayDateFormat(null)
  })

  it("sets every DatePicker's dateFormat token from the current display-format preference", () => {
    setDisplayDateFormat('dmy_dot')

    const { locale } = mountComposable()

    expect(locale.dateFormat).toBe('dd.mm.yy')
  })

  it('starts every week on Monday', () => {
    i18n.global.locale.value = 'deAT'

    const { locale } = mountComposable()

    expect(locale.firstDayOfWeek).toBe(1)
  })

  it('renders English month names by default', () => {
    const { locale } = mountComposable()

    expect(locale.monthNames?.[0]).toBe('January')
    expect(locale.monthNames?.[7]).toBe('August')
    expect(locale.monthNamesShort?.[0]).toBe('Jan')
  })

  it('renders German month names for the de-AT locale', () => {
    i18n.global.locale.value = 'deAT'

    const { locale } = mountComposable()

    expect(locale.monthNames?.[0]).toBe(deAtMonthName(0, 'long'))
    expect(locale.monthNames?.[0]).not.toBe('January')
    expect(locale.monthNames?.[7]).toBe(deAtMonthName(7, 'long'))
    expect(locale.monthNamesShort?.[0]).toBe(deAtMonthName(0, 'short'))
  })

  it('reacts to a later locale switch without remounting', async () => {
    const { locale } = mountComposable()
    expect(locale.monthNames?.[0]).toBe('January')

    i18n.global.locale.value = 'deAT'
    await nextTick()

    expect(locale.monthNames?.[0]).toBe(deAtMonthName(0, 'long'))
  })

  it('reacts to a later date-format preference change', async () => {
    const { locale } = mountComposable()
    expect(locale.dateFormat).toBe('yy-mm-dd')

    setDisplayDateFormat('mdy_slash')
    await nextTick()

    expect(locale.dateFormat).toBe('mm/dd/yy')
  })

  it('names the weekdays in the UI language, starting on Sunday as OpenVue expects', () => {
    i18n.global.locale.value = 'deAT'

    const { locale } = mountComposable()

    const sunday = new Intl.DateTimeFormat('de-AT', { weekday: 'long' }).format(new Date(2026, 10, 1))
    expect(locale.dayNames?.[0]).toBe(sunday)
    expect(locale.dayNamesMin?.every((name) => name.length <= 2 && !name.includes('.'))).toBe(true)
  })

  it("translates OpenVue's own text and keeps its count placeholder", () => {
    const { locale } = mountComposable()

    expect(locale.today).toBe('Today')
    expect(locale.emptyFilterMessage).toBe('No results found')
    expect(locale.selectionMessage).toBe('{0} items selected')
  })
})
