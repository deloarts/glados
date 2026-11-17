import { describe, it, expect } from 'vitest'
import { ref } from 'vue'

import { useArchivableOptions } from '../useArchivableOptions'

interface Widget {
  id: number
  name: string
  archived: boolean
}

function widget(overrides: Partial<Widget> = {}): Widget {
  return { id: 1, name: 'Widget', archived: false, ...overrides }
}

describe('useArchivableOptions', () => {
  it('keeps every item, sorting archived rows after live ones', () => {
    const items = ref<Widget[]>([
      widget({ id: 1, name: 'A', archived: true }),
      widget({ id: 2, name: 'B', archived: false }),
      widget({ id: 3, name: 'C', archived: true }),
      widget({ id: 4, name: 'D', archived: false }),
    ])

    const { sortedOptions } = useArchivableOptions(items)

    expect(sortedOptions.value.map((i) => i.id)).toEqual([2, 4, 1, 3])
  })

  it('preserves relative order within the live group and within the archived group', () => {
    const items = ref<Widget[]>([
      widget({ id: 1, archived: false }),
      widget({ id: 2, archived: false }),
      widget({ id: 3, archived: true }),
      widget({ id: 4, archived: true }),
    ])

    const { sortedOptions } = useArchivableOptions(items)

    expect(sortedOptions.value.map((i) => i.id)).toEqual([1, 2, 3, 4])
  })

  it('stays reactive to the source list', () => {
    const items = ref<Widget[]>([widget({ id: 1, archived: false })])
    const { sortedOptions } = useArchivableOptions(items)

    items.value = [widget({ id: 1, archived: true }), widget({ id: 2, archived: false })]

    expect(sortedOptions.value.map((i) => i.id)).toEqual([2, 1])
  })

  describe('isArchived', () => {
    it('returns false for null/undefined', () => {
      const { isArchived } = useArchivableOptions(ref<Widget[]>([]))
      expect(isArchived(null)).toBe(false)
      expect(isArchived(undefined)).toBe(false)
    })

    it('reads a single value', () => {
      const { isArchived } = useArchivableOptions(ref<Widget[]>([]))
      expect(isArchived(widget({ archived: true }))).toBe(true)
      expect(isArchived(widget({ archived: false }))).toBe(false)
    })

    it('returns true for an array (multi-select) when any selected value is archived', () => {
      const { isArchived } = useArchivableOptions(ref<Widget[]>([]))
      expect(
        isArchived([widget({ id: 1, archived: false }), widget({ id: 2, archived: true })]),
      ).toBe(true)
      expect(isArchived([widget({ id: 1, archived: false })])).toBe(false)
      expect(isArchived([])).toBe(false)
    })
  })
})
