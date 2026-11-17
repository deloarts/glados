import { describe, it, expect, afterEach } from 'vitest'
import { defineComponent, h } from 'vue'
import { createRouter, createMemoryHistory } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { usePublicBrandingStore } from '@/core/stores/publicBrandingStore'
import { usePageTitle } from '../usePageTitle'

function testRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/a', name: 'A', component: { template: '<div />' }, meta: { titleKey: 'todo.title' } },
      { path: '/b', name: 'B', component: { template: '<div />' }, meta: { titleKey: 'tools.title' } },
      { path: '/no-key', name: 'NoKey', component: { template: '<div />' } },
    ],
  })
}

const Host = defineComponent({
  setup() {
    const { setPageTitle } = usePageTitle()
    return { setPageTitle }
  },
  render() {
    return h('div')
  },
})

let wrapper: ReturnType<typeof mountWithApp> | null = null

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

describe('usePageTitle', () => {
  it("sets document.title from the route's titleKey", async () => {
    const router = testRouter()
    await router.push('/a')

    wrapper = mountWithApp(Host, { global: { plugins: [router] } })

    expect(document.title).toBe(`${i18n.global.t('todo.title')} · Glados`)
  })

  it('falls back to the app name alone when the route has no titleKey', async () => {
    const router = testRouter()
    await router.push('/no-key')

    wrapper = mountWithApp(Host, { global: { plugins: [router] } })

    expect(document.title).toBe('Glados')
  })

  it('re-applies the title on route change', async () => {
    const router = testRouter()
    await router.push('/a')

    wrapper = mountWithApp(Host, { global: { plugins: [router] } })
    expect(document.title).toBe(`${i18n.global.t('todo.title')} · Glados`)

    await router.push('/b')

    expect(document.title).toBe(`${i18n.global.t('tools.title')} · Glados`)
  })

  it('lets setPageTitle override the route title with the loaded entity', async () => {
    const router = testRouter()
    await router.push('/a')

    wrapper = mountWithApp(Host, { global: { plugins: [router] } })

    wrapper.vm.setPageTitle('PO-1234')

    expect(document.title).toBe('PO-1234 · Glados')
  })

  it('clears a setPageTitle override on the next navigation', async () => {
    const router = testRouter()
    await router.push('/a')

    wrapper = mountWithApp(Host, { global: { plugins: [router] } })
    wrapper.vm.setPageTitle('PO-1234')
    expect(document.title).toBe('PO-1234 · Glados')

    await router.push('/b')

    expect(document.title).toBe(`${i18n.global.t('tools.title')} · Glados`)
  })

  it('re-applies the title when the app name changes', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const brandingStore = usePublicBrandingStore()

    const router = testRouter()
    await router.push('/a')

    wrapper = mountWithApp(Host, { pinia, global: { plugins: [router] } })
    expect(document.title).toBe(`${i18n.global.t('todo.title')} · Glados`)

    // @ts-expect-error: test-only partial branding payload
    brandingStore.branding = { app_name: 'Acme Glados' }
    await wrapper.vm.$nextTick()

    expect(document.title).toBe(`${i18n.global.t('todo.title')} · Acme Glados`)
  })

  it('re-applies the title when the locale changes', async () => {
    const router = testRouter()
    await router.push('/a')

    wrapper = mountWithApp(Host, { global: { plugins: [router] } })
    expect(document.title).toBe(`${i18n.global.t('todo.title')} · Glados`)

    i18n.global.locale.value = 'deAT'
    await wrapper.vm.$nextTick()

    expect(document.title).toBe(`${i18n.global.t('todo.title', {}, { locale: 'deAT' })} · Glados`)

    i18n.global.locale.value = 'enGB'
  })
})

// A detail view calls usePageTitle() again for its own setPageTitle, deep
// inside AppLayout's component tree. It must reuse the instance AppLayout
// installed rather than start a second, independent one. Otherwise a
// locale or branding change later would re-apply the *installer's* (still
// unset) override and silently discard the detail view's title.
describe('usePageTitle - nested call reuses the installed instance', () => {
  it('lets a descendant set the title through the same instance', async () => {
    const Child = defineComponent({
      setup() {
        const { setPageTitle } = usePageTitle()
        return { setPageTitle }
      },
      render() {
        return h('div')
      },
    })
    const Parent = defineComponent({
      components: { Child },
      setup() {
        usePageTitle()
      },
      render() {
        return h(Child, { ref: 'child' })
      },
    })

    const router = testRouter()
    await router.push('/a')

    wrapper = mountWithApp(Parent, { global: { plugins: [router] } })
    expect(document.title).toBe(`${i18n.global.t('todo.title')} · Glados`)

    const child = wrapper.findComponent(Child)
    child.vm.setPageTitle('PO-1234')
    expect(document.title).toBe('PO-1234 · Glados')

    // The installer's own locale watcher must still see the child's
    // override, proof the two calls share one instance, not two.
    i18n.global.locale.value = 'deAT'
    await wrapper.vm.$nextTick()
    expect(document.title).toBe('PO-1234 · Glados')
    i18n.global.locale.value = 'enGB'
  })
})
