import { describe, it, expect, vi } from 'vitest'
import { defineComponent, ref } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'

import GladosButton from '../GladosButton'

function mountButton(initial: { loading: boolean; disabled?: boolean | '' }) {
  const onClick = vi.fn<() => void>()
  const loading = ref(initial.loading)
  const disabled = ref(initial.disabled)
  const Host = defineComponent({
    components: { GladosButton },
    setup: () => ({ loading, disabled, onClick }),
    template: `<GladosButton label="Save" :loading="loading" :disabled="disabled" @click="onClick" />`,
  })
  return { wrapper: mountWithApp(Host), loading, disabled, onClick }
}

describe('GladosButton', () => {
  it('stays disabled while loading even when the disabled binding is false', async () => {
    const { wrapper, onClick } = mountButton({ loading: true, disabled: false })

    const button = wrapper.find('button')
    expect(button.element.disabled).toBe(true)
    await button.trigger('click')
    expect(onClick).not.toHaveBeenCalled()
  })

  it('is enabled again once loading ends and clicks reach the listener', async () => {
    const { wrapper, loading, onClick } = mountButton({ loading: true, disabled: false })

    loading.value = false
    await wrapper.vm.$nextTick()

    const button = wrapper.find('button')
    expect(button.element.disabled).toBe(false)
    await button.trigger('click')
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('keeps an explicit disabled binding, including the bare attribute', () => {
    expect(mountButton({ loading: false, disabled: true }).wrapper.find('button').element.disabled).toBe(true)
    expect(mountButton({ loading: false, disabled: '' }).wrapper.find('button').element.disabled).toBe(true)
  })

  it('passes OpenVue props such as the label through', () => {
    const { wrapper } = mountButton({ loading: false })

    expect(wrapper.findComponent({ name: 'Button' }).props('label')).toBe('Save')
  })
})
