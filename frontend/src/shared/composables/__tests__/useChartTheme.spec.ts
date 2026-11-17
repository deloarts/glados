import { afterEach, describe, it, expect } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useChartTheme } from '../useChartTheme'

afterEach(() => {
  document.documentElement.style.removeProperty('--p-red-500')
  document.documentElement.style.removeProperty('--p-text-muted-color')
})

describe('useChartTheme', () => {
  it('falls back to the given colours when the document defines no tokens', () => {
    setActivePinia(createPinia())

    const theme = useChartTheme({ bar: ['--p-red-500', '#ef4444'] })

    expect(theme.value).toEqual({ bar: '#ef4444', text: '#6b7280', grid: '#e5e7eb' })
  })

  it('reads the series, text and grid colours from the document', () => {
    setActivePinia(createPinia())
    document.documentElement.style.setProperty('--p-red-500', '#ff0000')
    document.documentElement.style.setProperty('--p-text-muted-color', '#111111')

    const theme = useChartTheme({ bar: ['--p-red-500', '#ef4444'] })

    expect(theme.value.bar).toBe('#ff0000')
    expect(theme.value.text).toBe('#111111')
    expect(theme.value.grid).toBe('#e5e7eb')
  })
})
