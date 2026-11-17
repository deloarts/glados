import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import ChangelogCard from '../ChangelogCard.vue'

import type { ChangelogEntry } from '@/shared/utils/changelog'

function entry(overrides: Partial<ChangelogEntry> = {}): ChangelogEntry {
  return { timestamp: '2026-03-01 10:00', username: 'jdoe', message: 'Status changed', ...overrides }
}

interface Props {
  entries: ChangelogEntry[]
  loading: boolean
  error: boolean
}

function mountCard(props: Partial<Props> = {}) {
  return mountWithApp(ChangelogCard, {
    props: { entries: [], loading: false, error: false, ...props },
  })
}

describe('ChangelogCard', () => {
  it('shows the empty state when there are no entries', () => {
    expect(mountCard().text()).toContain('No changelog entries.')
  })

  it('shows a loading spinner only while there are no entries yet', () => {
    expect(mountCard({ loading: true }).find('.loading-state').exists()).toBe(true)
    expect(mountCard({ loading: true, entries: [entry()] }).find('.loading-state').exists()).toBe(false)
  })

  it('shows the section error state', () => {
    expect(mountCard({ error: true }).text()).toContain('Could not load this section.')
  })

  it('renders a row per entry with timestamp, user and message', () => {
    const wrapper = mountCard({ entries: [entry({ username: 'asmith', message: 'Created' })] })
    expect(wrapper.text()).toContain('2026-03-01 10:00')
    expect(wrapper.text()).toContain('asmith')
    expect(wrapper.text()).toContain('Created')
  })
})
