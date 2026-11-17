import { describe, it, expect } from 'vitest'

import {
  lotPositionStatusKey,
  lotPositionStatusSeverity,
  lotPositionStatusSeverityFor,
} from '../lotStatus'

// ORDERED_OR_QUEUED is one backend state covering both "a supplier order
// exists" and "a production order is queued". Which half is true is fixed
// by the position's kind, so only a MIXED position should ever render the
// combined label.
describe('lotPositionStatusKey', () => {
  it('reduces ordered_or_queued to "queued" for an internal position', () => {
    expect(lotPositionStatusKey('ordered_or_queued', 'internal')).toBe('queued')
  })

  it('reduces ordered_or_queued to "ordered" for an external position', () => {
    expect(lotPositionStatusKey('ordered_or_queued', 'external')).toBe('ordered')
  })

  it('keeps the combined label for a mixed position', () => {
    expect(lotPositionStatusKey('ordered_or_queued', 'mixed')).toBe('ordered_or_queued')
  })

  it('keeps the combined label when the kind is unknown', () => {
    expect(lotPositionStatusKey('ordered_or_queued', 'unassigned')).toBe('ordered_or_queued')
    expect(lotPositionStatusKey('ordered_or_queued', null)).toBe('ordered_or_queued')
    expect(lotPositionStatusKey('ordered_or_queued', undefined)).toBe('ordered_or_queued')
  })

  it('passes every other status straight through, whatever the kind', () => {
    for (const kind of ['internal', 'external', 'mixed', 'unassigned'] as const) {
      expect(lotPositionStatusKey('in_progress', kind)).toBe('in_progress')
      expect(lotPositionStatusKey('partially_completed', kind)).toBe('partially_completed')
      expect(lotPositionStatusKey('completed', kind)).toBe('completed')
      expect(lotPositionStatusKey('canceled', kind)).toBe('canceled')
    }
  })

  // A position is only EXTERNAL/MIXED because an OrderItem covers it, so
  // PENDING there means "on an order nobody has placed yet", not
  // "uncommitted": the ladder just doesn't advance until the item reaches
  // ORDERED.
  it('reads pending as "allocated" once an order covers the position', () => {
    expect(lotPositionStatusKey('pending', 'external')).toBe('allocated')
    expect(lotPositionStatusKey('pending', 'mixed')).toBe('allocated')
  })

  it('keeps a genuinely uncommitted position pending', () => {
    expect(lotPositionStatusKey('pending', 'unassigned')).toBe('pending')
    expect(lotPositionStatusKey('pending', 'internal')).toBe('pending')
    expect(lotPositionStatusKey('pending', null)).toBe('pending')
    expect(lotPositionStatusKey('pending', undefined)).toBe('pending')
  })

  describe('lotPositionStatusSeverityFor', () => {
    // warn, the same severity the demand tables give their own "allocated".
    it('lifts allocated out of pending grey', () => {
      expect(lotPositionStatusSeverityFor('pending', 'external')).toBe('warn')
      expect(lotPositionStatusSeverityFor('pending', 'mixed')).toBe('warn')
      expect(lotPositionStatusSeverityFor('pending', 'unassigned')).toBe('secondary')
    })

    it('falls back to the stored-status severity for unrefined statuses', () => {
      expect(lotPositionStatusSeverityFor('completed', 'internal')).toBe(
        lotPositionStatusSeverity.completed,
      )
      expect(lotPositionStatusSeverityFor('canceled', null)).toBe(
        lotPositionStatusSeverity.canceled,
      )
    })
  })

  it('never labels a born-internal inspection position as "ordered"', () => {
    // Inspection positions are created INTERNAL (create_lot.py's
    // born-internal pass), so this is the shape QA always takes.
    expect(lotPositionStatusKey('ordered_or_queued', 'internal')).not.toBe('ordered')
    expect(lotPositionStatusKey('ordered_or_queued', 'internal')).not.toBe('ordered_or_queued')
  })
})
