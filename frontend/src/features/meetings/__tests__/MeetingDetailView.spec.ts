import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { reactive } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeTestRouter, makeUserResponse } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useUsersStore } from '@/core/stores/usersStore'
import type { LiveSignal } from '@/core/realtime/types'
import { ANNA, makeCard, makeIssue, makeMeeting, makeTodo } from './meetingFixtures'
import type {
  MeetingCardResponse,
  MeetingDistributionEntryResponse,
  MeetingOpenPointResponse,
  MeetingResponse,
  MeetingSnapshotResponse,
} from '../types/meetingResponse'

vi.mock('../api/meetingsApi', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  return Object.fromEntries(Object.keys(actual).map((name) => [name, vi.fn<(...args: unknown[]) => unknown>()]))
})

// The live stream, with a way to hand the page a signal.
const handlers = new Map<string, Set<(signal: LiveSignal) => void>>()
const fakeLive = reactive({
  reconnectCount: 0,
  on(resource: string, handler: (signal: LiveSignal) => void) {
    const set = handlers.get(resource) ?? new Set()
    set.add(handler)
    handlers.set(resource, set)
    return () => set.delete(handler)
  },
})
vi.mock('@/core/realtime/liveStore', () => ({ useLiveStore: () => fakeLive }))

function signal(value: LiveSignal): void {
  handlers.get(value.resource)?.forEach((handler) => handler(value))
}

let granted = new Set<string>()
vi.mock('@/core/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: (permission: string) => granted.has(permission) }),
}))

import * as api from '../api/meetingsApi'
import MeetingDetailView from '../views/MeetingDetailView.vue'

vi.stubGlobal(
  'ResizeObserver',
  class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  },
)

function apiError(status: number): Error {
  return Object.assign(new Error(`HTTP ${status}`), {
    isAxiosError: true,
    response: { status, data: { detail: 'Failed' } },
  })
}

async function mountPage(meeting: MeetingResponse | Error) {
  if (meeting instanceof Error) vi.mocked(api.getMeeting).mockRejectedValue(meeting)
  else vi.mocked(api.getMeeting).mockResolvedValue(structuredClone(meeting))
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = makeUserResponse({ id: 1, full_name: 'Jonas Example' })
  useUsersStore().users = [
    { ...ANNA, is_active: true, is_service_account: false, is_shared_account: false, is_systemuser: false },
  ]
  const router = makeTestRouter([
    {
      path: '/workspace/projects/:id(\\d+)/meeting-notes/:meetingId(\\d+)',
      name: 'ProjectMeeting',
      component: MeetingDetailView,
    },
  ])
  await router.push('/workspace/projects/142/meeting-notes/21')
  await router.isReady()
  const wrapper = mountWithApp(MeetingDetailView, { pinia, global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, router }
}

function distributionEntry(): MeetingDistributionEntryResponse {
  return {
    journal_entry_id: 70,
    journal_entry_public_id: '00000000-0000-0000-0000-000000000070',
    kind: 'sent',
    at: '2026-11-06T10:00:00Z',
    actor: ANNA,
    actor_full_name: 'Anna Generic',
    issue: { issue_number: 1, draft: false, revision: '1' },
    language: 'enGB',
    options: { include_todos: true, include_internal: false, list_documents: true },
    report_version: '0.1.0',
    byte_size: 1000,
    sha256: 'f'.repeat(64),
    recipients: ['thomas@muster.example'],
    cc: [],
    subject: 'Minutes',
    copies: null,
    print_job_id: null,
    snapshot_id: 7,
  }
}

function snapshotOf(card: MeetingCardResponse): MeetingSnapshotResponse {
  return {
    id: 7,
    public_id: '00000000-0000-0000-0000-000000000007',
    meeting_id: 21,
    journal_entry_id: 70,
    kind: 'sent',
    created: '2026-11-06T10:00:00Z',
    actor: ANNA,
    issue: { issue_number: 1, draft: false, revision: '1' },
    language: 'enGB',
    options: { include_todos: true, include_internal: false, list_documents: true },
    byte_size: 1000,
    sha256: 'f'.repeat(64),
    meeting: {
      meeting_number: 'MTG-26-0021',
      name: 'Design Review Gripper',
      starts_at: '2026-11-06T08:00:00Z',
      ends_at: '2026-11-06T09:30:00Z',
      location: null,
      next_meeting_date: null,
      next_meeting_time: null,
      next_meeting_location: null,
      owner_kind: 'project',
      owner_id: 142,
      owner_number: '26-0142',
    },
    cards: [{ ...card, decisions: [], todos: [] }],
    attendees: [],
    files: [],
    attachments: [],
    recipients: ['thomas@muster.example'],
    cc: [],
    subject: 'Minutes',
  }
}

function button(wrapper: Awaited<ReturnType<typeof mountPage>>['wrapper'], testId: string) {
  return wrapper.find(`[data-testid="${testId}"]`)
}

beforeEach(() => {
  granted = new Set(['write:meetings', 'manage:meetings'])
  handlers.clear()
  vi.mocked(api.getMeetingDistribution).mockResolvedValue([])
  vi.mocked(api.getMeetingOpenPoints).mockResolvedValue([])
  vi.mocked(api.getMeetingIssue).mockResolvedValue(makeIssue())
  vi.mocked(api.fetchMeetingFileBlob).mockResolvedValue(new Blob())
})

describe('MeetingDetailView', () => {
  it('says so when the meeting does not exist', async () => {
    const { wrapper } = await mountPage(apiError(404))

    expect(wrapper.find('[data-testid="meeting-not-found"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="meeting-load-error"]').exists()).toBe(false)
  })

  it('says so when the meeting could not be loaded', async () => {
    const { wrapper } = await mountPage(apiError(500))

    expect(wrapper.find('[data-testid="meeting-load-error"]').exists()).toBe(true)
  })

  it('shows a valid meeting with its cards and its editing actions', async () => {
    const { wrapper } = await mountPage(makeMeeting())

    expect(wrapper.find('[data-testid="meeting-info-number"]').text()).toBe('MTG-26-0021')
    expect(wrapper.find('[data-testid="meeting-info-validity"]').text()).toBe('Valid')
    expect(wrapper.find('[data-testid="meeting-info-owner"]').text()).toBe('Project 26-0142')
    expect(wrapper.find('[data-testid="meeting-card-body"]').html()).toContain('<strong>40,000 cycles</strong>')
    expect(button(wrapper, 'meeting-edit').attributes('disabled')).toBeUndefined()
    expect(button(wrapper, 'meeting-add-card').attributes('disabled')).toBeUndefined()
    expect(button(wrapper, 'meeting-mark-invalid').exists()).toBe(true)
    expect(button(wrapper, 'meeting-restore').exists()).toBe(false)
    expect(button(wrapper, 'meeting-follow-up').exists()).toBe(true)
    // Print and Send open once the issue the notes carry is known.
    expect(button(wrapper, 'meeting-print').attributes('disabled')).toBeUndefined()
    expect(button(wrapper, 'meeting-send').attributes('disabled')).toBeDefined()
    expect(wrapper.find('[data-testid="meeting-invalid-notice"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="meeting-open-points"]').exists()).toBe(false)
  })

  it('shows an invalid meeting read-only with its reason and offers Restore', async () => {
    const { wrapper } = await mountPage(
      makeMeeting({
        valid: false,
        invalid_at: '2026-11-07T10:00:00Z',
        invalid_by: ANNA,
        invalid_reason: 'Recorded against the wrong project',
      }),
    )

    expect(wrapper.find('[data-testid="meeting-info-validity"]').text()).toBe('Invalid')
    expect(wrapper.find('[data-testid="meeting-invalid-notice"]').text()).toContain('Recorded against the wrong project')
    expect(button(wrapper, 'meeting-restore').attributes('disabled')).toBeUndefined()
    const shown = [
      'meeting-mark-invalid',
      'meeting-edit',
      'meeting-add-card',
      'meeting-add-file',
      'meeting-follow-up',
      'meeting-card-delete',
      'meeting-card-edit',
      'meeting-add-card-bottom',
    ].filter((testId) => button(wrapper, testId).exists())
    expect(shown).toEqual([])
  })

  it('keeps the actions visible but disabled without the rights', async () => {
    granted = new Set()
    const { wrapper } = await mountPage(makeMeeting())

    expect(button(wrapper, 'meeting-edit').attributes('disabled')).toBeDefined()
    expect(button(wrapper, 'meeting-add-card').attributes('disabled')).toBeDefined()
    expect(button(wrapper, 'meeting-mark-invalid').attributes('disabled')).toBeDefined()
    expect(button(wrapper, 'meeting-card-delete').attributes('disabled')).toBeDefined()
    expect(button(wrapper, 'meeting-card-scope').attributes('disabled')).toBeDefined()
  })

  it('lets a manager restore an invalid meeting only with manage:meetings', async () => {
    granted = new Set(['write:meetings'])
    const { wrapper } = await mountPage(makeMeeting({ valid: false, invalid_reason: 'Wrong project' }))

    expect(button(wrapper, 'meeting-restore').attributes('disabled')).toBeDefined()
  })

  it('shows the open points of a follow-up meeting', async () => {
    const point: MeetingOpenPointResponse = {
      todo: makeTodo({ id: 77, meeting_id: 18, card_id: 4, title: 'Confirm the delivery week' }),
      meeting: { id: 18, meeting_number: 'MTG-26-0018', name: 'Kick-off Line 2' },
      meeting_starts_at: '2026-10-28T13:00:00Z',
      card_scope: 'Milestones',
    }
    vi.mocked(api.getMeetingOpenPoints).mockResolvedValue([point])
    const { wrapper } = await mountPage(
      makeMeeting({ follow_up_of: { id: 18, meeting_number: 'MTG-26-0018', name: 'Kick-off Line 2' } }),
    )

    const card = wrapper.find('[data-testid="meeting-open-points"]')
    expect(card.text()).toContain('Confirm the delivery week')
    expect(card.text()).toContain('MTG-26-0018')
    expect(wrapper.find('[data-testid="meeting-info-follow-up-of"]').text()).toBe('Follows MTG-26-0018')
  })

  it('shows who else is editing a card until they stop', async () => {
    const { wrapper } = await mountPage(makeMeeting())

    signal({ resource: 'meeting-card-presence', id: 1, action: 'updated', actor_id: ANNA.id })
    await flushPromises()
    expect(wrapper.find('[data-testid="meeting-card-presence"]').text()).toBe('Anna Generic is editing')

    signal({ resource: 'meeting-card-presence', id: 1, action: 'deleted', actor_id: ANNA.id })
    await flushPromises()
    expect(wrapper.find('[data-testid="meeting-card-presence"]').exists()).toBe(false)
  })

  it('leaves out the heartbeats of the viewer', async () => {
    const { wrapper } = await mountPage(makeMeeting())

    signal({ resource: 'meeting-card-presence', id: 1, action: 'updated', actor_id: 1 })
    await flushPromises()

    expect(wrapper.find('[data-testid="meeting-card-presence"]').exists()).toBe(false)
  })

  it('tags the cards changed or added since the last send and offers to show the changes', async () => {
    vi.mocked(api.getMeetingIssue).mockResolvedValue(
      makeIssue({
        issue_number: 1,
        last_sent_at: '2026-11-06T10:00:00Z',
        print: { issue_number: 1, draft: true, revision: '1-draft' },
        send: { issue_number: 2, draft: false, revision: '2' },
        changed_card_ids: [1],
        added_card_ids: [2],
      }),
    )
    vi.mocked(api.getMeetingDistribution).mockResolvedValue([distributionEntry()])
    const { wrapper } = await mountPage(makeMeeting({ cards: [makeCard(), makeCard({ id: 2, position: 1, scope: 'Schedule' })] }))

    expect(wrapper.find('[data-testid="meeting-card-changed-1"]').text()).toBe('Changed After Sending')
    expect(wrapper.find('[data-testid="meeting-card-added-2"]').text()).toBe('Added After Sending')
    expect(wrapper.find('[data-testid="meeting-card-changed-2"]').exists()).toBe(false)
    const notice = wrapper.find('[data-testid="meeting-changed-notice"]')
    expect(notice.text()).toContain('1 changed, 1 added and 0 removed cards')
    expect(button(wrapper, 'meeting-changed-show').exists()).toBe(true)
    // Sending again needs send:mail, so it stays visible but disabled.
    expect(button(wrapper, 'meeting-changed-send').attributes('disabled')).toBeDefined()
  })

  it('tags nothing while the notes are unchanged since the last send', async () => {
    vi.mocked(api.getMeetingIssue).mockResolvedValue(makeIssue({ issue_number: 1, last_sent_at: '2026-11-06T10:00:00Z' }))
    const { wrapper } = await mountPage(makeMeeting())

    expect(wrapper.find('[data-testid="meeting-card-changed-1"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="meeting-changed-notice"]').exists()).toBe(false)
  })

  it('opens the snapshot of a distribution entry as sent and with the changes since', async () => {
    vi.mocked(api.getMeetingDistribution).mockResolvedValue([distributionEntry()])
    vi.mocked(api.getMeetingSnapshot).mockResolvedValue(snapshotOf(makeCard({ body: 'The cups show wear.' })))
    const { wrapper } = await mountPage(makeMeeting())

    expect(button(wrapper, 'meeting-distribution-view-70').text()).toBe('View as Sent')
    await button(wrapper, 'meeting-distribution-changes-70').trigger('click')
    await flushPromises()

    expect(api.getMeetingSnapshot).toHaveBeenCalledWith(21, 7)
    const change = document.body.querySelector('[data-testid="meeting-snapshot-change-1"]')
    expect(change?.getAttribute('data-status')).toBe('changed')
    wrapper.unmount()
    document.body.innerHTML = ''
  })

  it('reads the meeting again when it changes elsewhere', async () => {
    await mountPage(makeMeeting())
    vi.useFakeTimers()
    vi.mocked(api.getMeeting).mockResolvedValue(makeMeeting({ cards: [makeCard({ body: 'Changed elsewhere' })] }))

    signal({ resource: 'meetings', id: 21, action: 'updated', actor_id: ANNA.id })
    await vi.advanceTimersByTimeAsync(600)
    vi.useRealTimers()

    expect(api.getMeeting).toHaveBeenCalledTimes(2)
  })
})
