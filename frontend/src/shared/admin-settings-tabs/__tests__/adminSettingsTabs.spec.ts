import { describe, it, expect } from 'vitest'
import { createApp, defineComponent, h, type Plugin } from 'vue'
import { mount } from '@vue/test-utils'

import {
  registerAdminSettingsTab,
  useRegisteredAdminSettingsTabs,
  type AdminSettingsTab,
} from '../adminSettingsTabs'

function tab(value: string, order: number): AdminSettingsTab {
  return { value, icon: 'mdi-cog', component: { render: () => null }, order }
}

function capture(plugins: Plugin[]): readonly AdminSettingsTab[] {
  let tabs!: readonly AdminSettingsTab[]
  mount(
    defineComponent({
      setup() {
        tabs = useRegisteredAdminSettingsTabs()
        return () => h('div')
      },
    }),
    { global: { plugins } },
  )
  return tabs
}

describe('admin settings tab registry', () => {
  it('reads no tabs when no feature registered one', () => {
    expect(capture([])).toEqual([])
  })

  it('collects the tabs of every plugin into one list', () => {
    const first: Plugin = { install: (app) => registerAdminSettingsTab(app, tab('a', 15)) }
    const second: Plugin = { install: (app) => registerAdminSettingsTab(app, tab('b', 25)) }

    expect(capture([first, second]).map((registered) => registered.value)).toEqual(['a', 'b'])
  })

  it('keeps the tabs of one app apart from another', () => {
    const app = createApp({ render: () => null })
    registerAdminSettingsTab(app, tab('a', 15))

    expect(capture([])).toEqual([])
  })
})
