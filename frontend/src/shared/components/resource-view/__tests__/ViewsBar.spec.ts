import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'

import ViewsBar from '../ViewsBar.vue'

function mountBar(props: { showArchived?: boolean; hasActiveFilters?: boolean } = {}) {
  return mountWithApp(ViewsBar, {
    props: {
      idPrefix: 'widgets',
      hasActiveFilters: false,
      ...props,
    },
  })
}

function button(bar: ReturnType<typeof mountBar>, label: string) {
  return bar.findAllComponents({ name: 'Button' }).find((b) => b.props('label') === label)
}

describe('ViewsBar - Show Archived toggle', () => {
  it('is hidden entirely when showArchived is left undefined (a non-archivable resource)', () => {
    const bar = mountBar({})

    expect(button(bar, i18n.global.t('common.showArchived'))).toBeUndefined()

    bar.unmount()
  })

  it('renders next to Clear when showArchived is a boolean, in text style while off', () => {
    const bar = mountBar({ showArchived: false })

    const toggle = button(bar, i18n.global.t('common.showArchived'))
    expect(toggle).toBeDefined()
    expect(toggle!.props('text')).toBe(true)

    bar.unmount()
  })

  it('switches to solid style while showArchived is on', () => {
    const bar = mountBar({ showArchived: true })

    expect(button(bar, i18n.global.t('common.showArchived'))!.props('text')).toBe(false)

    bar.unmount()
  })

  it('emits toggle-show-archived when clicked', async () => {
    const bar = mountBar({ showArchived: false })

    await button(bar, i18n.global.t('common.showArchived'))!.trigger('click')

    expect(bar.emitted('toggle-show-archived')).toHaveLength(1)

    bar.unmount()
  })
})
