import { beforeEach, describe, expect, it } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { stubPhoneScreen } from '@/test-utils/phoneScreen'
import { i18n } from '@/core/i18n'

import ViewsBar from '../ViewsBar.vue'

beforeEach(() => {
  stubPhoneScreen(true)
})

describe('ViewsBar on a phone', () => {
  it('keeps sync, clear and the search box, and leaves the desktop views out', async () => {
    const bar = mountWithApp(ViewsBar, {
      props: {
        idPrefix: 'widgets',
        hasActiveFilters: true,
        showArchived: false,
        groupByItems: [{ label: 'Status' }],
        search: '',
        'onUpdate:search': (value: string | undefined) => bar.setProps({ search: value }),
      },
      slots: { 'start-extra': '<button class="own-extra">Timeline</button>' },
    })

    const labels = bar.findAllComponents({ name: 'Button' }).map((b) => b.attributes('aria-label'))
    expect(labels).toEqual([i18n.global.t('common.sync'), i18n.global.t('common.clear')])
    expect(bar.find('.own-extra').exists()).toBe(false)
    expect(bar.findComponent({ name: 'SplitButton' }).exists()).toBe(false)

    await bar.get('input').setValue('bracket')
    expect(bar.emitted('update:search')?.at(-1)).toEqual(['bracket'])

    bar.unmount()
  })
})
