import { describe, it, expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import ContextMenu from 'openvue/contextmenu'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { disabledItemTooltipPt } from '../menuItemTooltip'

import type { MenuItem } from 'openvue/menuitem'

const model: MenuItem[] = [
  { label: 'Archive', disabled: true, title: 'The machine still has 2 open orders.' },
  { label: 'Edit', title: 'Edit the machine' },
  { label: 'Restore', disabled: true },
]

const Host = defineComponent({
  setup() {
    const cm = ref<{ show: (event: Event) => void } | null>(null)
    return { cm }
  },
  render() {
    return h(ContextMenu, { ref: 'cm', model, pt: disabledItemTooltipPt })
  },
})

describe('disabledItemTooltipPt', () => {
  it('gives only a disabled entry with a title a native title attribute', async () => {
    const wrapper = mountWithApp(Host, { attachTo: document.body })
    ;(wrapper.vm as unknown as { cm: { show: (event: Event) => void } }).cm.show(
      new MouseEvent('contextmenu', { clientX: 10, clientY: 10 }),
    )
    await flushPromises()

    const links = Array.from(document.body.querySelectorAll('[role="menuitem"] a'))
    const titleOf = (label: string) =>
      links.find((link) => link.textContent?.includes(label))?.getAttribute('title') ?? null

    expect(titleOf('Archive')).toBe('The machine still has 2 open orders.')
    expect(titleOf('Edit')).toBeNull()
    expect(titleOf('Restore')).toBeNull()

    wrapper.unmount()
  })
})
