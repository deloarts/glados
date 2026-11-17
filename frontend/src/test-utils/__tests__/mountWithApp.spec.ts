import { describe, it, expect } from 'vitest'
import { defineComponent, inject, ref } from 'vue'
import { defineStore, createPinia, setActivePinia } from 'pinia'
import { useToast } from 'openvue/usetoast'
import Button from 'openvue/button'

import { mountWithApp } from '../mountWithApp'

// A throwaway store that exists only to prove Pinia is wired, not a real
// feature store. Each test creates its own Pinia instance, so re-using this
// id across tests never collides.
const useProbeStore = defineStore('mountWithAppProbe', () => {
  const label = ref('default')
  return { label }
})

// Exercises all four standard plugins at once: OpenVue (Button renders),
// i18n ($t resolves a real key), Pinia (reads a store), and ToastService
// (useToast().add doesn't throw for lack of a provider).
const ProbeComponent = defineComponent({
  name: 'ProbeComponent',
  components: { PvButton: Button },
  setup() {
    const store = useProbeStore()
    const toast = useToast()
    const extra = inject<boolean>('extraFlag', false)
    return { store, toast, extra }
  },
  template: `<div><PvButton :label="$t('common.save')" /><span class="store-label">{{ store.label }}</span></div>`,
})

describe('mountWithApp', () => {
  it('wires Pinia, OpenVue, i18n, and ToastService by default', () => {
    const wrapper = mountWithApp(ProbeComponent)

    const button = wrapper.findComponent({ name: 'Button' })
    expect(button.exists()).toBe(true)
    // A resolved translation, not the raw dotted key.
    expect(button.props('label')).toBe('Save')
    expect(wrapper.find('.store-label').text()).toBe('default')

    // ToastService is installed: calling .add() must not throw for want of
    // a provider (it would with no plugin installed).
    const vm = wrapper.vm as unknown as { toast: { add: (o: unknown) => void } }
    expect(() => vm.toast.add({ severity: 'info', detail: 'x', life: 100 })).not.toThrow()

    wrapper.unmount()
  })

  it('accepts a caller-supplied Pinia instance to seed store state before mount', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useProbeStore().label = 'seeded'

    const wrapper = mountWithApp(ProbeComponent, { pinia })

    expect(wrapper.find('.store-label').text()).toBe('seeded')

    wrapper.unmount()
  })

  it('falls back to a fresh Pinia instance per call when none is supplied', () => {
    const first = mountWithApp(ProbeComponent)
    const firstVm = first.vm as unknown as { store: { label: string } }
    firstVm.store.label = 'mutated by the first mount'
    first.unmount()

    // A second call with no pinia option must not see the first mount's
    // mutation. Each gets its own createPinia(), not a shared/ambient one.
    const second = mountWithApp(ProbeComponent)
    expect(second.find('.store-label').text()).toBe('default')

    second.unmount()
  })

  it('merges caller-supplied global.plugins after the standard four instead of replacing them', () => {
    const extraPlugin = {
      install(app: { provide: (key: string, value: unknown) => void }) {
        app.provide('extraFlag', true)
      },
    }

    const wrapper = mountWithApp(ProbeComponent, {
      global: { plugins: [extraPlugin] },
    })

    // The standard plugins are still active...
    expect(wrapper.findComponent({ name: 'Button' }).props('label')).toBe('Save')
    // ...and the caller's own plugin also took effect.
    const vm = wrapper.vm as unknown as { extra: boolean }
    expect(vm.extra).toBe(true)

    wrapper.unmount()
  })

  it('passes other global options (stubs, provide) through untouched alongside the standard plugins', () => {
    const wrapper = mountWithApp(ProbeComponent, {
      global: {
        provide: { extraFlag: true },
        stubs: { Button: { template: '<button class="stub-button" /> ' } },
      },
    })

    // i18n/store still resolve even though Button is stubbed out.
    expect(wrapper.find('.store-label').text()).toBe('default')
    expect(wrapper.find('.stub-button').exists()).toBe(true)
    const vm = wrapper.vm as unknown as { extra: boolean }
    expect(vm.extra).toBe(true)

    wrapper.unmount()
  })
})
