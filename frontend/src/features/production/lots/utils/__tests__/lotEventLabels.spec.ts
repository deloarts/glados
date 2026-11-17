import { describe, it, expect } from 'vitest'
import { createI18n } from 'vue-i18n'

import {
  FALLBACK_LOT_EVENT_ICON,
  LOT_EVENT_ICONS,
  humanizeLotEventType,
  lotEventIcon,
  lotEventLabel,
} from '../lotEventLabels'

function i18nWith(events: Record<string, string>) {
  const i18n = createI18n({
    legacy: false,
    locale: 'enGB',
    messages: { enGB: { production: { lots: { detail: { audit: { events } } } } } },
  })
  return { t: i18n.global.t, te: i18n.global.te }
}

describe('lotEventLabel', () => {
  it('returns the translation of an event type that has one', () => {
    const i18n = i18nWith({ lot_completed: 'Lot completed' })

    expect(lotEventLabel('lot_completed', i18n)).toBe('Lot completed')
  })

  it('names an event type without a translation in words, not by its message key', () => {
    const i18n = i18nWith({ lot_completed: 'Lot completed' })

    expect(lotEventLabel('lot_status_changed', i18n)).toBe('Lot Status Changed')
  })
})

describe('humanizeLotEventType', () => {
  it('capitalises each word and drops empty ones', () => {
    expect(humanizeLotEventType('pieces_lost_at_receipt')).toBe('Pieces Lost At Receipt')
    expect(humanizeLotEventType('lot__scrapped_')).toBe('Lot Scrapped')
  })
})

describe('lotEventIcon', () => {
  it('has an icon for the status change and scrapped events', () => {
    expect(lotEventIcon('lot_status_changed')).toBe(LOT_EVENT_ICONS.lot_status_changed)
    expect(lotEventIcon('lot_scrapped')).toBe(LOT_EVENT_ICONS.lot_scrapped)
    expect(LOT_EVENT_ICONS.lot_scrapped).not.toBe(FALLBACK_LOT_EVENT_ICON)
  })

  it('shows a neutral icon for an event type it does not know', () => {
    expect(lotEventIcon('lot_teleported')).toBe(FALLBACK_LOT_EVENT_ICON)
  })
})
