import { describe, it, expect, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'

import ControlsBar from '../ControlsBar.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'

let wrapper: ReturnType<typeof mount> | null = null

function mountBar(slots: Record<string, string> = {}) {
  wrapper = mountWithApp(ControlsBar, {
    slots: { start: '<button class="own-control">Create</button>', ...slots },
  })
  return wrapper
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

// ControlsBar exposes a bare `#handbook` slot rather than rendering
// HelpButton itself, since only the caller knows which doc explains its view.
// These specs cover the slot mechanics only; HelpButton's own doc-lookup
// behaviour is covered by its own spec.
describe('ControlsBar', () => {
  it('renders the feature controls it wraps', () => {
    const bar = mountBar()

    expect(bar.findComponent({ name: 'Toolbar' }).exists()).toBe(true)
    expect(bar.find('.own-control').exists()).toBe(true)
  })

  it('renders whatever a caller passes into the #handbook slot', () => {
    const bar = mountBar({ handbook: '<button class="explain">Explain</button>' })

    expect(bar.find('[data-testid="controls-bar-end"] .explain').exists()).toBe(true)
  })

  it('leaves the end of the bar empty when no caller fills the #handbook slot', () => {
    // A slot makes an undocumented (or deliberately opted-out) view's lack of
    // an explain button explicit, rather than ControlsBar deciding for it.
    const bar = mountBar()

    expect(bar.get('[data-testid="controls-bar-end"]').element.children.length).toBe(0)
  })

  it('keeps a feature its own end slot, with #handbook content after it', () => {
    const bar = mountBar({
      end: '<button class="own-end">Refresh</button>',
      handbook: '<button class="explain">Explain</button>',
    })

    const end = bar.get('[data-testid="controls-bar-end"]')
    const children = [...end.element.children].map((c) => c.className)
    expect(children[0]).toContain('own-end')
    expect(children.at(-1)).toContain('explain')
  })
})
