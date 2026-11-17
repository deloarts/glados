import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { VueWrapper } from '@vue/test-utils'

import ControlsBar from '../ControlsBar.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { stubPhoneScreen } from '@/test-utils/phoneScreen'

let wrapper: VueWrapper | null = null

function mountBar(slots: Record<string, string>) {
  wrapper = mountWithApp(ControlsBar, { slots, attachTo: document.body })
  return wrapper
}

beforeEach(() => {
  stubPhoneScreen(true)
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

describe('ControlsBar on a phone', () => {
  it('moves the actions into a closed menu and keeps the end and handbook in the bar', () => {
    const bar = mountBar({
      start: '<button class="own-control">Create</button>',
      end: '<button class="own-end">Share</button>',
      handbook: '<button class="explain">Explain</button>',
    })

    const menu = bar.get('[data-testid="controls-bar-menu"]')
    expect(menu.find('.own-control').exists()).toBe(true)
    expect(menu.isVisible()).toBe(false)
    expect(menu.find('.own-end').exists()).toBe(false)
    expect(bar.find('.own-end').isVisible()).toBe(true)
    expect(bar.find('.explain').isVisible()).toBe(true)
  })

  it('opens the menu from the Actions button and closes it once an action runs', async () => {
    const bar = mountBar({ start: '<button class="own-control">Create</button>' })

    await bar.get('[data-testid="controls-bar-actions"]').trigger('click')
    expect(bar.get('[data-testid="controls-bar-menu"]').isVisible()).toBe(true)

    await bar.get('.own-control').trigger('click')
    expect(bar.get('[data-testid="controls-bar-menu"]').isVisible()).toBe(false)
  })

  it('shows no Actions button when the bar has no actions', () => {
    const bar = mountBar({ handbook: '<button class="explain">Explain</button>' })

    expect(bar.find('[data-testid="controls-bar-actions"]').exists()).toBe(false)
  })
})
