import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'

import ItemDemandsControlsBar from '../ItemDemandsControlsBar.vue'

function mountBar(
  props: { i18nPrefix?: string; canCreate?: boolean; createBlocked?: string } = {},
  slots = {},
) {
  return mountWithApp(ItemDemandsControlsBar, {
    props: {
      i18nPrefix: 'boughtItems.demands.controls',
      canCreate: true,
      ...props,
    },
    slots,
  })
}

function button(bar: ReturnType<typeof mountBar>, label: string) {
  return bar.findAllComponents({ name: 'Button' }).find((b) => b.props('label') === label)
}

describe('ItemDemandsControlsBar', () => {
  it('resolves the New label from the given i18n prefix', () => {
    const bar = mountBar({ i18nPrefix: 'sourceItems.demands.controls' })

    expect(button(bar, i18n.global.t('sourceItems.demands.controls.new'))).toBeDefined()

    bar.unmount()
  })

  it('disables New when canCreate is false', () => {
    const bar = mountBar({ canCreate: false })

    // OpenVue's Button reads `disabled` off $attrs rather than declaring it
    // as its own prop, so it must be asserted as a rendered attribute.
    expect(
      button(bar, i18n.global.t('boughtItems.demands.controls.new'))!.attributes('disabled'),
    ).toBeDefined()

    bar.unmount()
  })

  it('names the reason on the wrapper of a disabled New', () => {
    const blocked = 'This needs the permission Write Demand Items.'
    const bar = mountBar({ canCreate: false, createBlocked: blocked })

    const newButton = button(bar, i18n.global.t('boughtItems.demands.controls.new'))!
    const span = newButton.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
    expect(span?.$_ptooltipValue).toBe(blocked)

    bar.unmount()
  })

  it('emits create when New is clicked', async () => {
    const bar = mountBar()

    await button(bar, i18n.global.t('boughtItems.demands.controls.new'))!.trigger('click')

    expect(bar.emitted('create')).toHaveLength(1)

    bar.unmount()
  })

  it('places the actions slot content behind New', () => {
    const bar = mountBar(
      {},
      {
        actions: '<button class="manage-orders-stub">Manage orders</button>',
      },
    )

    const start = bar.get('[data-testid="controls-bar-start"]')
    const texts = [...start.element.children].map((el) => el.textContent ?? '')

    const newIndex = texts.findIndex((t) => t.includes(i18n.global.t('boughtItems.demands.controls.new')))
    const manageIndex = texts.findIndex((t) => t.includes('Manage orders'))

    expect(newIndex).toBeGreaterThanOrEqual(0)
    expect(manageIndex).toBeGreaterThan(newIndex)

    bar.unmount()
  })
})
