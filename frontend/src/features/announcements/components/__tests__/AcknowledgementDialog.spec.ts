import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useAnnouncementsStore } from '../../stores/announcementsStore'
import type { PendingAcknowledgement } from '../../types/announcementsTypes'

vi.mock('../../api/acknowledgeAnnouncement', () => ({
  acknowledgeAnnouncement: vi.fn<() => Promise<void>>().mockResolvedValue(undefined),
}))

import AcknowledgementDialog from '../AcknowledgementDialog.vue'
import { acknowledgeAnnouncement } from '../../api/acknowledgeAnnouncement'

function makeAck(overrides: Partial<PendingAcknowledgement> = {}): PendingAcknowledgement {
  return {
    public_id: 'a1',
    text: 'First notice',
    severity: 'info',
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function mountDialog() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(AcknowledgementDialog, { pinia, attachTo: document.body })
  return { wrapper, store: useAnnouncementsStore() }
}

describe('AcknowledgementDialog', () => {
  beforeEach(() => {
    // Dialog teleports to document.body, clear it between tests, or a
    // previous test's teleported content (or its Toast, if one fired) would
    // still be there when the next test reads document.body.textContent.
    document.body.innerHTML = ''
  })

  it('is not visible when nothing is pending', () => {
    const { wrapper } = mountDialog()

    expect(wrapper.findComponent({ name: 'Dialog' }).props('visible')).toBe(false)
  })

  // Ground rule: the dialog must not be closable by
  // Escape, the mask, or a close icon; only the Acknowledge button may close it.
  it('cannot be closed by Escape, the mask, or a close icon', async () => {
    const { wrapper, store } = mountDialog()
    store.pendingAcknowledgements = [makeAck()]
    await wrapper.vm.$nextTick()

    const dialog = wrapper.findComponent({ name: 'Dialog' })
    expect(dialog.props('closable')).toBe(false)
    expect(dialog.props('closeOnEscape')).toBe(false)
    expect(dialog.props('dismissableMask')).toBe(false)
    expect(dialog.props('draggable')).toBe(false)
  })

  // Dialog teleports to document.body by default (OpenVue's appendTo), so
  // its content lives outside wrapper.element's own subtree. CSS-selector
  // finds and whole-wrapper .text() must go through document.body instead,
  // same reasoning as SystemUserWarningDialog.spec.ts. findComponent()
  // still works everywhere below since it walks the component tree, not
  // the DOM.
  it.each([
    ['info', 'mdi-information'],
    ['warning', 'mdi-alert'],
    ['danger', 'mdi-alert-octagon'],
  ] as const)('the header is a large centred %s icon and nothing else', async (severity, icon) => {
    const { wrapper, store } = mountDialog()
    store.pendingAcknowledgements = [makeAck({ severity })]
    await wrapper.vm.$nextTick()

    const header = document.body.querySelector('.acknowledge-header')
    expect(header).not.toBeNull()
    // Icon only, no title text next to it: the admin's message below is
    // the whole point of the dialog.
    expect(header!.textContent?.trim()).toBe('')
    expect(header!.querySelector('.acknowledge-icon')?.classList.contains(icon)).toBe(true)
  })

  it('shows the acknowledgement text with pre-line whitespace', async () => {
    const { wrapper, store } = mountDialog()
    store.pendingAcknowledgements = [makeAck({ text: 'Line one\nLine two' })]
    await wrapper.vm.$nextTick()

    const text = document.body.querySelector('.acknowledge-text')
    expect(text).not.toBeNull()
    expect(text!.textContent).toContain('Line one')
    expect(text!.textContent).toContain('Line two')
  })

  it('confirming acknowledges the current one and advances to the next', async () => {
    const { wrapper, store } = mountDialog()
    store.pendingAcknowledgements = [
      makeAck({ public_id: 'a1', text: 'First' }),
      makeAck({ public_id: 'a2', text: 'Second' }),
    ]
    await wrapper.vm.$nextTick()
    expect(document.body.textContent).toContain('First')

    await wrapper.findComponent({ name: 'Button' }).trigger('click')
    await flushPromises()

    expect(acknowledgeAnnouncement).toHaveBeenCalledWith('a1')
    expect(wrapper.findComponent({ name: 'Dialog' }).props('visible')).toBe(true)
    expect(document.body.textContent).toContain('Second')

    await wrapper.findComponent({ name: 'Button' }).trigger('click')
    await flushPromises()

    expect(acknowledgeAnnouncement).toHaveBeenCalledWith('a2')
    expect(wrapper.findComponent({ name: 'Dialog' }).props('visible')).toBe(false)
  })

  it('keeps the dialog open when acknowledging fails', async () => {
    vi.mocked(acknowledgeAnnouncement).mockRejectedValueOnce(new Error('network down'))
    const { wrapper, store } = mountDialog()
    store.pendingAcknowledgements = [makeAck()]
    await wrapper.vm.$nextTick()

    await wrapper.findComponent({ name: 'Button' }).trigger('click')
    await flushPromises()

    expect(wrapper.findComponent({ name: 'Dialog' }).props('visible')).toBe(true)
    expect(store.pendingAcknowledgements).toHaveLength(1)
  })
})
