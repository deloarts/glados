import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'

import { i18n } from '@/core/i18n'

// ProductionQueueBoard owns the whole kanban (its own store fetch, live
// refresh, drag/drop); none of that is this view's concern (it takes no
// props and is mounted with none), so it's stubbed the same way heavy
// children are elsewhere in this suite.
vi.mock('../../components/ProductionQueueBoard.vue', () => ({
  default: { name: 'ProductionQueueBoard', template: '<div class="production-queue-board-stub" />' },
}))

import ProductionQueueView from '../ProductionQueueView.vue'

function mountView() {
  return mount(ProductionQueueView, {
    global: { plugins: [createPinia(), i18n] },
  })
}

describe('ProductionQueueView', () => {
  it('mounts ProductionQueueBoard with no props - the view has no data or wiring of its own', () => {
    const wrapper = mountView()

    const board = wrapper.findComponent({ name: 'ProductionQueueBoard' })
    expect(board.exists()).toBe(true)
    expect(Object.keys(board.props())).toHaveLength(0)
  })
})
