import { describe, it, expect } from 'vitest'

import { createSection, runSection } from '../useCatalogueItemSections'

describe('createSection', () => {
  it('starts empty, not loading, no error, not truncated', () => {
    const section = createSection<number[]>([])
    expect(section).toEqual({ data: [], loading: false, error: false, truncated: false })
  })

  it('uses the given empty value as the rest state', () => {
    const section = createSection<string | null>(null)
    expect(section.data).toBeNull()
  })
})

describe('runSection', () => {
  it('unwraps a bare array result', async () => {
    const section = createSection<number[]>([])
    await runSection(section, async () => [1, 2, 3])
    expect(section.data).toEqual([1, 2, 3])
    expect(section.error).toBe(false)
    expect(section.loading).toBe(false)
  })

  it('unwraps an { items, total } envelope', async () => {
    const section = createSection<number[]>([])
    await runSection(section, async () => ({ items: [1, 2], total: 2 }))
    expect(section.data).toEqual([1, 2])
  })

  it('sets loading true for the duration of a non-quiet call', async () => {
    const section = createSection<number[]>([])
    let sawLoading = false
    await runSection(section, async () => {
      sawLoading = section.loading
      return [1]
    })
    expect(sawLoading).toBe(true)
    expect(section.loading).toBe(false)
  })

  it('never flips loading for a quiet call', async () => {
    const section = createSection<number[]>([])
    let sawLoading = false
    await runSection(
      section,
      async () => {
        sawLoading = section.loading
        return [1]
      },
      { quiet: true },
    )
    expect(sawLoading).toBe(false)
    expect(section.loading).toBe(false)
  })

  it('flags truncated once the result reaches the limit', async () => {
    const section = createSection<number[]>([])
    await runSection(section, async () => [1, 2], { limit: 2 })
    expect(section.truncated).toBe(true)
  })

  it('does not flag truncated below the limit', async () => {
    const section = createSection<number[]>([])
    await runSection(section, async () => [1], { limit: 2 })
    expect(section.truncated).toBe(false)
  })

  it('sets error and keeps stale data when the loader rejects', async () => {
    const section = createSection<number[]>([1, 2])
    await runSection(section, async () => {
      throw new Error('boom')
    })
    expect(section.error).toBe(true)
    expect(section.data).toEqual([1, 2])
    expect(section.loading).toBe(false)
  })

  it('clears a previous error on a subsequent success', async () => {
    const section = createSection<number[]>([])
    await runSection(section, async () => {
      throw new Error('boom')
    })
    expect(section.error).toBe(true)
    await runSection(section, async () => [1])
    expect(section.error).toBe(false)
    expect(section.data).toEqual([1])
  })

  it('leaves data/error/truncated untouched when isCurrent is false on resolve', async () => {
    const section = createSection<number[]>([1, 2])
    await runSection(section, async () => [9, 9, 9], { limit: 3, isCurrent: () => false })
    expect(section.data).toEqual([1, 2])
    expect(section.error).toBe(false)
    expect(section.truncated).toBe(false)
  })

  it('leaves data/error untouched when isCurrent is false on reject', async () => {
    const section = createSection<number[]>([1, 2])
    await runSection(
      section,
      async () => {
        throw new Error('boom')
      },
      { isCurrent: () => false },
    )
    expect(section.data).toEqual([1, 2])
    expect(section.error).toBe(false)
  })

  it('still writes data when isCurrent is true', async () => {
    const section = createSection<number[]>([])
    await runSection(section, async () => [1, 2], { isCurrent: () => true })
    expect(section.data).toEqual([1, 2])
  })

  it('does not clear loading for a discarded (isCurrent=false) non-quiet call', async () => {
    const section = createSection<number[]>([])
    // Simulate a newer call already having set loading back to true after
    // this (stale) call's own loader started, so the stale call settling must
    // not stomp on it.
    await runSection(
      section,
      async () => {
        section.loading = true
        return [1]
      },
      { isCurrent: () => false },
    )
    expect(section.loading).toBe(true)
  })
})
