import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeCard, makeMeeting } from './meetingFixtures'
import type { MeetingCardResponse } from '../types/meetingResponse'
import type { MeetingCardUpdateRequest } from '../types/meetingRequest'

const updateMeetingCard = vi.fn<(meetingId: number, cardId: number, body: MeetingCardUpdateRequest) => Promise<MeetingCardResponse>>()
vi.mock('../api/meetingsApi', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  return {
    ...Object.fromEntries(Object.keys(actual).map((name) => [name, vi.fn<(...args: unknown[]) => Promise<void>>().mockResolvedValue(undefined)])),
    updateMeetingCard: (meetingId: number, cardId: number, body: MeetingCardUpdateRequest) =>
      updateMeetingCard(meetingId, cardId, body),
  }
})

import MeetingCard from '../components/MeetingCard.vue'

// jsdom measures no layout, and ProseMirror asks a range for its rectangles
// when it scrolls the selection into view.
for (const proto of [Range.prototype, Element.prototype]) {
  Object.defineProperty(proto, 'getClientRects', { configurable: true, value: () => [] })
  Object.defineProperty(proto, 'getBoundingClientRect', { configurable: true, value: () => new DOMRect() })
}

let wrapper: VueWrapper | null = null

function mountCard(card: MeetingCardResponse = makeCard()) {
  wrapper = mountWithApp(MeetingCard, {
    attachTo: document.body,
    props: {
      meeting: makeMeeting({ cards: [card] }),
      card,
      canWrite: true,
      writeBlocked: '',
      editors: [],
      ownerOptions: [],
      imageUrl: () => undefined,
      imageVersion: 0,
      uploadImage: async () => null,
    },
  })
  return wrapper
}

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.body.innerHTML = ''
})

describe('MeetingCard', () => {
  it('shows the card in its reading view with its scope', async () => {
    const view = mountCard()
    await flushPromises()

    expect(view.find('[data-testid="meeting-card-scope"]').text()).toContain('Vacuum gripper')
    expect(view.find('[data-testid="meeting-card-body"]').html()).toContain('<strong>40,000 cycles</strong>')
    expect(view.find('[data-testid="meeting-card-editor"]').exists()).toBe(false)
  })

  it('edits the card in Visual and Markdown mode over the same text and saves it', async () => {
    const view = mountCard()
    updateMeetingCard.mockResolvedValue(makeCard({ edit_version: 4, body: 'New text' }))

    await view.find('[data-testid="meeting-card-edit"]').trigger('click')
    await flushPromises()
    expect(view.find('[data-testid="meeting-card-editor"]').exists()).toBe(true)
    expect(view.find('.ProseMirror').html()).toContain('<strong>40,000 cycles</strong>')

    const markdownMode = view.findAll('[data-testid="meeting-editor-mode"] button').at(1)
    await markdownMode?.trigger('click')
    await flushPromises()
    const textarea = view.find('[data-testid="meeting-editor-markdown"]')
    expect((textarea.element as HTMLTextAreaElement).value).toBe('The cups show wear after **40,000 cycles**.')

    await textarea.setValue('New text')
    await view.find('[data-testid="meeting-card-save"]').trigger('click')
    await flushPromises()

    expect(updateMeetingCard).toHaveBeenCalledWith(21, 1, expect.objectContaining({ body: 'New text', expected_edit_version: 3 }))
    expect(view.emitted('updated')).toEqual([[expect.objectContaining({ edit_version: 4 })]])
  })

  it('puts Internal, Save and Cancel in the header before History and Delete, without the card info', async () => {
    const view = mountCard()
    await view.find('[data-testid="meeting-card-edit"]').trigger('click')
    await flushPromises()

    const header = view.get('header')
    const order = header.findAll('[data-testid]').map((element) => element.attributes('data-testid'))
    expect(order.filter((id) => id !== 'meeting-card-scope')).toEqual([
      'meeting-card-internal',
      'meeting-card-save',
      'meeting-card-cancel',
      'meeting-card-history-button',
      'meeting-card-delete',
    ])
    expect(view.text()).not.toContain('Created by')
  })

  it('offers a draft left from before a reload', async () => {
    localStorage.setItem(
      'glados.meetings.cardDraft.1',
      JSON.stringify({ editVersion: 3, body: 'Unsaved draft', internal: false, savedAt: '2026-11-10T09:00:00Z' }),
    )
    const view = mountCard()
    await flushPromises()

    expect(view.find('[data-testid="meeting-card-draft"]').exists()).toBe(true)
    await view.find('[data-testid="meeting-draft-restore"]').trigger('click')
    await flushPromises()

    expect(view.find('.ProseMirror').text()).toContain('Unsaved draft')
  })
})
