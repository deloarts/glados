import { watchEffect } from 'vue'
import { usePrimeVue } from 'openvue/config'

import { i18n } from '@/core/i18n'
import { getPickerDateFormat, monthName, weekdayName } from '@/core/utils/dates'

// The OpenVue locale keys that carry text, translated under common.openVue.
const TEXT_KEYS = [
  'startsWith',
  'contains',
  'notContains',
  'endsWith',
  'equals',
  'notEquals',
  'noFilter',
  'lt',
  'lte',
  'gt',
  'gte',
  'dateIs',
  'dateIsNot',
  'dateBefore',
  'dateAfter',
  'clear',
  'apply',
  'matchAll',
  'matchAny',
  'addRule',
  'removeRule',
  'accept',
  'reject',
  'choose',
  'upload',
  'cancel',
  'completed',
  'pending',
  'chooseYear',
  'chooseMonth',
  'chooseDate',
  'prevDecade',
  'nextDecade',
  'prevYear',
  'nextYear',
  'prevMonth',
  'nextMonth',
  'today',
  'weekHeader',
  'emptyFilterMessage',
  'emptySearchMessage',
  'emptyMessage',
  'emptySelectionMessage',
  'noFileChosenMessage',
] as const

// OpenVue fills "{0}" in these itself, so the placeholder is handed over as is.
const COUNT_KEYS = ['searchMessage', 'selectionMessage', 'fileChosenMessage'] as const

// OpenVue's day name arrays start on Sunday, and 2026-11-01 is one.
function weekdayNames(style: 'long' | 'short'): string[] {
  return Array.from({ length: 7 }, (_, d) => weekdayName(new Date(2026, 10, 1 + d), style))
}

/**
 * Keeps OpenVue's own text and every `<DatePicker>` in step with the user's
 * language and date-format preference.
 *
 * OpenVue resolves a DatePicker's pattern as
 * `this.dateFormat || $primevue.config.locale.dateFormat`, and that config is
 * `reactive()`. So writing it here drives all ~40 pickers at once, and no
 * component needs to pass `dateFormat` itself. Call this once from the root
 * component, because `usePrimeVue()` needs an injection context.
 *
 * Month and day names come from Intl in the UI language: the `d_mon_y` preset
 * renders "06 Aug 2026", and the picker has to parse back the same
 * abbreviations the display uses. The week starts on Monday in every
 * language, as the ISO weeks the planning pages count do. The remaining text,
 * such as "Today", "Clear" and the empty messages of select overlays, comes
 * from the locale files.
 */
export function useOpenVueLocale(): void {
  const openVue = usePrimeVue()

  watchEffect(() => {
    // Typed optional, but OpenVue always merges its own defaults in, so this
    // guard is only here to satisfy the compiler.
    const locale = openVue.config.locale
    if (!locale) return

    locale.dateFormat = getPickerDateFormat()
    locale.firstDayOfWeek = 1
    locale.monthNames = Array.from({ length: 12 }, (_, m) => monthName(m + 1, 'long'))
    locale.monthNamesShort = Array.from({ length: 12 }, (_, m) => monthName(m + 1, 'short'))
    // Only writes, never reads, the config: reading back what this effect
    // wrote would make it trigger itself.
    const shortDays = weekdayNames('short')
    locale.dayNames = weekdayNames('long')
    locale.dayNamesShort = shortDays
    // The calendar header has room for two letters ("Mo", "Di").
    locale.dayNamesMin = shortDays.map((name) => name.replace('.', '').slice(0, 2))

    const { t } = i18n.global
    for (const key of TEXT_KEYS) locale[key] = t(`common.openVue.${key}`)
    for (const key of COUNT_KEYS) locale[key] = t(`common.openVue.${key}`, { count: '{0}' })
  })
}
