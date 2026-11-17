import { describe, it, expect } from 'vitest'
import { computed, defineComponent, h, type Plugin } from 'vue'
import { mount } from '@vue/test-utils'

import {
  registerAccountSection,
  registerAccountTab,
  useRegisteredAccountSections,
  useRegisteredAccountTabs,
  type AccountSection,
  type AccountTab,
} from '../accountPage'

const EMPTY = { render: () => null }

function section(key: string, order: number): AccountSection {
  return { key, component: EMPTY, order, useVisible: () => computed(() => true) }
}

function capture(plugins: Plugin[]) {
  let tabs!: readonly AccountTab[]
  let sections!: readonly AccountSection[]
  mount(
    defineComponent({
      setup() {
        tabs = useRegisteredAccountTabs()
        sections = useRegisteredAccountSections()
        return () => h('div')
      },
    }),
    { global: { plugins } },
  )
  return { tabs, sections }
}

describe('account page registry', () => {
  it('reads no tabs and no sections when no feature registered one', () => {
    expect(capture([])).toEqual({ tabs: [], sections: [] })
  })

  it('collects tabs and sorts sections by their order', () => {
    const plugin: Plugin = {
      install(app) {
        registerAccountTab(app, {
          value: 'extra',
          labelKey: 'common.save',
          component: EMPTY,
          order: 15,
          useAccess: () => ({
            visible: computed(() => true),
            allowed: computed(() => true),
            icon: computed(() => 'mdi-cog'),
          }),
        })
        registerAccountSection(app, section('later', 20))
        registerAccountSection(app, section('earlier', 10))
      },
    }

    const { tabs, sections } = capture([plugin])

    expect(tabs.map((tab) => tab.value)).toEqual(['extra'])
    expect(sections.map((registered) => registered.key)).toEqual(['earlier', 'later'])
  })
})
