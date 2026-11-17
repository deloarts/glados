import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { defineComponent, h } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { stubPhoneScreen } from '@/test-utils/phoneScreen'
import { offeredOnPhone, usePhoneLayout } from '../usePhoneLayout'

const Blank = { render: () => null }

const ROUTES: RouteRecordRaw[] = [
  { path: '/dashboard', name: 'Dashboard', component: Blank, meta: { phone: true } },
  { path: '/settings', name: 'Settings', component: Blank },
  {
    path: '/resources/:tab?',
    name: 'Resources',
    component: Blank,
    meta: { phone: { param: 'tab', tabs: ['customers', 'suppliers'] } },
  },
]

async function mountOn(path: string) {
  const router = createRouter({ history: createMemoryHistory(), routes: ROUTES })
  await router.push(path)
  await router.isReady()

  let layout!: ReturnType<typeof usePhoneLayout>
  const Host = defineComponent({
    setup() {
      layout = usePhoneLayout()
      return () => h('div')
    },
  })
  const wrapper = mountWithApp(Host, { global: { plugins: [router] } })
  return { wrapper, router, layout }
}

describe('offeredOnPhone', () => {
  const resolve = (path: string) =>
    createRouter({ history: createMemoryHistory(), routes: ROUTES }).resolve(path)

  it('offers a page flagged as a whole', () => {
    expect(offeredOnPhone(resolve('/dashboard'))).toBe(true)
  })

  it('does not offer a page without a phone scope', () => {
    expect(offeredOnPhone(resolve('/settings'))).toBe(false)
  })

  it('offers only the listed tabs of a tab route', () => {
    expect(offeredOnPhone(resolve('/resources/suppliers'))).toBe(true)
    expect(offeredOnPhone(resolve('/resources/holidays'))).toBe(false)
  })

  it('offers a tab route without its param, which shows the view default', () => {
    expect(offeredOnPhone(resolve('/resources'))).toBe(true)
  })

  it('never gates a path that matches no route', () => {
    expect(offeredOnPhone(resolve('/nowhere'))).toBe(true)
  })
})

describe('usePhoneLayout', () => {
  let mounted: Awaited<ReturnType<typeof mountOn>> | null = null

  beforeEach(() => {
    stubPhoneScreen(true)
  })

  afterEach(() => {
    mounted?.wrapper.unmount()
    mounted = null
  })

  it('shows the notice on a phone for a desktop page only', async () => {
    mounted = await mountOn('/settings')
    expect(mounted.layout.showDesktopNotice.value).toBe(true)

    await mounted.router.push('/dashboard')
    expect(mounted.layout.showDesktopNotice.value).toBe(false)
  })

  it('offers only the phone tabs in phone mode', async () => {
    mounted = await mountOn('/resources/customers')
    expect(mounted.layout.tabOffered('suppliers')).toBe(true)
    expect(mounted.layout.tabOffered('holidays')).toBe(false)
  })

  it('shows a page in full on request until the user leaves its route', async () => {
    mounted = await mountOn('/resources/holidays')
    expect(mounted.layout.showDesktopNotice.value).toBe(true)

    mounted.layout.showDesktopAnyway()
    expect(mounted.layout.phoneMode.value).toBe(false)
    expect(mounted.layout.showDesktopNotice.value).toBe(false)
    expect(mounted.layout.tabOffered('holidays')).toBe(true)

    // Another tab of the same route keeps the full page.
    await mounted.router.push('/resources/printers')
    expect(mounted.layout.showDesktopNotice.value).toBe(false)

    await mounted.router.push('/dashboard')
    await flushPromises()
    await mounted.router.push('/resources/holidays')
    expect(mounted.layout.showDesktopNotice.value).toBe(true)
  })

  it('stays out of the way on a desktop', async () => {
    stubPhoneScreen(false)
    mounted = await mountOn('/settings')
    expect(mounted.layout.isPhone.value).toBe(false)
    expect(mounted.layout.showDesktopNotice.value).toBe(false)
    expect(mounted.layout.tabOffered('holidays')).toBe(true)
  })
})
