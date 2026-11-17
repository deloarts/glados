import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import CakeEasterEgg from '../CakeEasterEgg.vue'
import { rollCakeWindow, weekKeyOf } from '@/core/utils/cakeSchedule'

const CAKE_ICON = '[aria-label="Cake"]'

async function mountEgg() {
  const wrapper = mountWithApp(CakeEasterEgg)
  await flushPromises()
  return wrapper
}

/** Puts a window in storage that is open at `now`. */
function storeOpenWindow(now: Date): void {
  localStorage.setItem(
    'cakeWindow',
    JSON.stringify({
      weekKey: weekKeyOf(now),
      startsAt: now.getTime() - 60_000,
      durationMs: 60 * 60_000,
    }),
  )
}

describe('CakeEasterEgg', () => {
  beforeEach(() => {
    localStorage.clear()
    document.body.innerHTML = ''
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('stays hidden outside its weekly window', async () => {
    vi.useFakeTimers()
    // Tuesday 2026-08-11, 16:30, well outside 09:00-14:00.
    vi.setSystemTime(new Date(2026, 7, 11, 16, 30))

    const wrapper = await mountEgg()

    expect(wrapper.find(CAKE_ICON).exists()).toBe(false)
  })

  it('appears inside its window', async () => {
    vi.useFakeTimers()
    const now = new Date(2026, 7, 11, 10, 30)
    vi.setSystemTime(now)
    storeOpenWindow(now)

    const wrapper = await mountEgg()

    expect(wrapper.find(CAKE_ICON).exists()).toBe(true)
  })

  it('keeps the same window across reloads rather than rerolling', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 7, 11, 8, 0))

    await mountEgg()
    const first = localStorage.getItem('cakeWindow')

    await mountEgg()

    expect(localStorage.getItem('cakeWindow')).toBe(first)
  })

  it('rerolls once the stored window belongs to a past week', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 7, 11, 8, 0))
    localStorage.setItem('cakeWindow', JSON.stringify(rollCakeWindow(new Date(2026, 6, 6, 8, 0))))

    await mountEgg()

    expect(JSON.parse(localStorage.getItem('cakeWindow')!).weekKey).toBe('2026-08-10')
  })

  // The sequence ends by reloading the page, so "already eaten" has to outlive
  // the component or the cake would be back in the footer immediately.
  it('stays retired for the rest of the window once eaten', async () => {
    vi.useFakeTimers()
    const now = new Date(2026, 7, 11, 10, 30)
    vi.setSystemTime(now)
    storeOpenWindow(now)
    localStorage.setItem('cakeEaten', String(now.getTime() - 60_000))

    const wrapper = await mountEgg()

    expect(wrapper.find(CAKE_ICON).exists()).toBe(false)
  })

  it('offers cake again once a new window is rolled', async () => {
    vi.useFakeTimers()
    const now = new Date(2026, 7, 11, 10, 30)
    vi.setSystemTime(now)
    storeOpenWindow(now)
    // An eaten marker from some earlier window.
    localStorage.setItem('cakeEaten', '1')

    const wrapper = await mountEgg()

    expect(wrapper.find(CAKE_ICON).exists()).toBe(true)
  })

  // Otherwise the overrides would be single-use, which makes the thing
  // untestable after the first run.
  it('lets ?cake=1 through even when this window has been eaten', async () => {
    vi.useFakeTimers()
    const now = new Date(2026, 7, 11, 10, 30)
    vi.setSystemTime(now)
    storeOpenWindow(now)
    localStorage.setItem('cakeEaten', String(now.getTime() - 60_000))
    vi.stubGlobal('location', { ...globalThis.location, search: '?cake=1' })

    const wrapper = await mountEgg()

    expect(wrapper.find(CAKE_ICON).exists()).toBe(true)
    vi.unstubAllGlobals()
  })

  it('survives a corrupt stored window', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 7, 11, 8, 0))
    localStorage.setItem('cakeWindow', 'not json')

    await expect(mountEgg()).resolves.toBeTruthy()
    expect(JSON.parse(localStorage.getItem('cakeWindow')!).weekKey).toBe('2026-08-10')
  })

  describe('the two dialogs', () => {
    beforeEach(() => {
      vi.useFakeTimers()
      const now = new Date(2026, 7, 11, 10, 30)
      vi.setSystemTime(now)
      storeOpenWindow(now)
    })

    it('asks first, and the first yes only opens the second dialog', async () => {
      const wrapper = await mountEgg()
      await wrapper.find(CAKE_ICON).trigger('click')
      await flushPromises()

      expect(document.body.textContent).toContain('Do you want cake?')
      expect(document.body.textContent).not.toContain('Do you really want cake?')

      // The dialogs teleport to body, so the buttons are not in the wrapper.
      const yes = [...document.body.querySelectorAll('button')].find((b) =>
        b.textContent?.includes('Yes'),
      )!
      yes.click()
      await flushPromises()

      expect(document.body.textContent).toContain('Do you really want cake?')
      // Still nothing running, since the sequence needs the second yes.
      expect(document.documentElement.classList.contains('cake-glitch')).toBe(false)
    })

    it('retires the cake when declined', async () => {
      const wrapper = await mountEgg()
      await wrapper.find(CAKE_ICON).trigger('click')
      await flushPromises()

      const no = [...document.body.querySelectorAll('button')].find((b) =>
        b.textContent?.includes('No'),
      )!
      no.click()
      await flushPromises()

      expect(wrapper.find(CAKE_ICON).exists()).toBe(false)
    })
  })
})
