import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { Pinia } from 'pinia'
import { defineComponent, h, nextTick, ref } from 'vue'
import type { WatchSource } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useLoadingBarStore } from '@/core/stores/loadingBarStore'
import { watchLoadingBar } from '../useLoadingBar'

let pinia: Pinia

// mountWithApp defaults to its own fresh Pinia instance, which would give
// the mounted component a different loadingBarStore than the one this spec
// spies on. Passing the active instance through keeps them the same store.
function mountWatcher(source: WatchSource<boolean>) {
  return mountWithApp(
    defineComponent({
      setup() {
        watchLoadingBar(source)
        return () => h('div')
      },
    }),
    { pinia },
  )
}

describe('watchLoadingBar', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
  })

  it('starts the loading bar immediately when the source is already true', () => {
    const store = useLoadingBarStore()
    const startSpy = vi.spyOn(store, 'start')

    const wrapper = mountWatcher(ref(true))

    expect(startSpy).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('does not start the loading bar when the source starts out false', () => {
    const store = useLoadingBarStore()
    const startSpy = vi.spyOn(store, 'start')

    const wrapper = mountWatcher(ref(false))

    expect(startSpy).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('starts and stops the loading bar in step as the source flips back and forth', async () => {
    const store = useLoadingBarStore()
    const startSpy = vi.spyOn(store, 'start')
    const stopSpy = vi.spyOn(store, 'stop')
    const source = ref(false)

    const wrapper = mountWatcher(source)

    source.value = true
    await nextTick()
    expect(startSpy).toHaveBeenCalledTimes(1)
    expect(stopSpy).not.toHaveBeenCalled()

    source.value = false
    await nextTick()
    expect(stopSpy).toHaveBeenCalledTimes(1)

    source.value = true
    await nextTick()
    expect(startSpy).toHaveBeenCalledTimes(2)

    wrapper.unmount()
  })

  it('stops the loading bar on unmount while still active, balancing an unmount mid-load', () => {
    const store = useLoadingBarStore()
    const stopSpy = vi.spyOn(store, 'stop')

    const wrapper = mountWatcher(ref(true))
    wrapper.unmount()

    expect(stopSpy).toHaveBeenCalledTimes(1)
  })

  it('does not call stop again on unmount when it was already inactive', () => {
    const store = useLoadingBarStore()
    const stopSpy = vi.spyOn(store, 'stop')

    const wrapper = mountWatcher(ref(false))
    wrapper.unmount()

    expect(stopSpy).not.toHaveBeenCalled()
  })
})
