import { describe, it, expect } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { defineComponent } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import LotsViewsBar from '../LotsViewsBar.vue'
import { useProductionLotsFiltersStore } from '../../stores/productionLotsFiltersStore'

import type { MenuItem } from 'openvue/menuitem'

function mountBar(compact: boolean) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:p(.*)*', component: defineComponent({ template: '<div />' }) }],
  })
  return mountWithApp(LotsViewsBar, { props: { compact }, global: { plugins: [router] } })
}

const label = (key: string) => i18n.global.t(`production.lots.views.${key}`)

function splitButton(wrapper: ReturnType<typeof mountBar>, testId: string) {
  return wrapper
    .findAllComponents({ name: 'SplitButton' })
    .find((b) => b.attributes('data-testid') === testId)!
}

function run(items: MenuItem[], text: string): void {
  const item = items.find((i) => i.label === text)!
  ;(item.command as () => void)()
}

describe('LotsViewsBar', () => {
  it('shows the modes and quick filters as buttons on a full bar', () => {
    const wrapper = mountBar(false)

    expect(wrapper.text()).toContain(label('simpleMode'))
    expect(wrapper.text()).toContain(label('hideCompleted'))
    expect(wrapper.find('[data-testid="lots-views-modes"]').exists()).toBe(false)
  })

  it('puts the quick filters behind a split button that toggles and clears them', async () => {
    const wrapper = mountBar(true)
    const store = useProductionLotsFiltersStore()

    expect(wrapper.text()).not.toContain(label('hideCompleted'))
    const filters = splitButton(wrapper, 'lots-views-quick-filters')
    run(filters.props('model') as MenuItem[], label('hideCompleted'))
    run(filters.props('model') as MenuItem[], label('needsApproval'))
    await wrapper.vm.$nextTick()

    expect(store.hideCompleted).toBe(true)
    expect(store.needsApprovalOnly).toBe(true)
    expect(filters.props('label')).toBe(i18n.global.t('production.lots.views.quickFiltersCount', { n: 2 }))

    filters.vm.$emit('click', new MouseEvent('click'))
    expect(store.hideCompleted).toBe(false)
    expect(store.needsApprovalOnly).toBe(false)
  })

  it('puts the modes behind a split button that picks one and returns to Column Mode', async () => {
    const wrapper = mountBar(true)
    const store = useProductionLotsFiltersStore()
    const modes = splitButton(wrapper, 'lots-views-modes')

    run(modes.props('model') as MenuItem[], label('modes.widescreen'))
    expect(store.widescreenMode).toBe(true)

    run(modes.props('model') as MenuItem[], label('modes.simple'))
    await wrapper.vm.$nextTick()
    expect(store.simpleMode).toBe(true)
    expect(modes.props('label')).toBe(label('modes.simple'))

    modes.vm.$emit('click', new MouseEvent('click'))
    expect(store.simpleMode).toBe(false)
    expect(store.widescreenMode).toBe(false)
  })
})
