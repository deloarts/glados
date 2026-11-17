import { beforeEach, describe, expect, it } from 'vitest'

import { i18n } from '@/core/i18n'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

import { useKpiFormat } from '../useKpiFormat'

describe('useKpiFormat', () => {
  beforeEach(() => {
    i18n.global.locale.value = 'enGB'
  })

  it('shows a ratio as a percentage with one decimal and no space before the sign', () => {
    expect(useKpiFormat().formatPercent(0.1234)).toBe('12.3%')
  })

  it('uses the decimal comma in German', () => {
    i18n.global.locale.value = 'deAT'
    expect(useKpiFormat().formatPercent(0.1234)).toBe('12,3%')
  })

  it('shows a quantity with up to two decimals', () => {
    const { formatQuantity } = useKpiFormat()
    expect(formatQuantity(3)).toBe('3')
    expect(formatQuantity(2.456)).toBe('2.46')
  })

  it('shows days with one decimal', () => {
    expect(useKpiFormat().formatDays(4)).toBe('4.0')
  })

  it('shows the empty placeholder for a missing ratio or day count', () => {
    const { formatPercent, formatDays } = useKpiFormat()
    expect(formatPercent(null)).toBe(getEmptyPlaceholder())
    expect(formatDays(null)).toBe(getEmptyPlaceholder())
  })
})
