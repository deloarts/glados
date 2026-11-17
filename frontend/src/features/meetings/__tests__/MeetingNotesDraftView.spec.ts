import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeTestRouter } from '@/test-utils/factories'
import { makeDraft } from './meetingNotesDraftFixtures'
import { makeMeeting } from './meetingFixtures'
import type {
  MeetingNotesDraftApplyRequest,
  MeetingNotesDraftApplyResponse,
  MeetingNotesDraftResponse,
} from '../types/meetingNotesDraft'

const getMeetingNotesDraft = vi.fn<(id: number) => Promise<MeetingNotesDraftResponse>>()
const applyMeetingNotesDraft =
  vi.fn<(id: number, body: MeetingNotesDraftApplyRequest) => Promise<MeetingNotesDraftApplyResponse>>()
const discardMeetingNotesDraft = vi.fn<(id: number) => Promise<void>>()
vi.mock('../api/meetingNotesDraftsApi', () => ({
  getMeetingNotesDraft: (id: number) => getMeetingNotesDraft(id),
  applyMeetingNotesDraft: (id: number, body: MeetingNotesDraftApplyRequest) => applyMeetingNotesDraft(id, body),
  discardMeetingNotesDraft: (id: number) => discardMeetingNotesDraft(id),
}))

let granted = new Set<string>()
vi.mock('@/core/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: (permission: string) => granted.has(permission) }),
}))

import MeetingNotesDraftView from '../views/MeetingNotesDraftView.vue'

async function mountAt(path: string, permissions: string[] = ['write:meetings']) {
  const router = makeTestRouter([
    { path: '/meeting-notes-drafts/:id(\\d+)', name: 'MeetingNotesDraft', component: MeetingNotesDraftView },
    { path: '/workspace/projects/:id/meeting-notes/:meetingId', name: 'ProjectMeeting', component: { template: '<div />' } },
  ])
  await router.push(path)
  await router.isReady()
  granted = new Set(permissions)
  const wrapper = mountWithApp(MeetingNotesDraftView, { global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, router }
}

beforeEach(() => {
  getMeetingNotesDraft.mockReset()
  applyMeetingNotesDraft.mockReset()
  getMeetingNotesDraft.mockResolvedValue(makeDraft())
  applyMeetingNotesDraft.mockResolvedValue({ meeting: makeMeeting({ id: 21 }) })
})

describe('MeetingNotesDraftView', () => {
  it('shows the draft with the agent notes, its people and its cards', async () => {
    const { wrapper } = await mountAt('/meeting-notes-drafts/5')

    expect(getMeetingNotesDraft).toHaveBeenCalledWith(5)
    expect(wrapper.find('[data-testid="draft-notice"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="draft-card-note-0"]').text()).toContain('Second line unreadable')
    expect(wrapper.findAll('[data-testid="draft-person"]')).toHaveLength(4)
    expect(wrapper.findAll('[data-testid^="draft-card-include-"]')).toHaveLength(2)
  })

  it('applies the reviewed draft and opens the meeting', async () => {
    const { wrapper, router } = await mountAt('/meeting-notes-drafts/5')

    await wrapper.find('[data-testid="draft-apply"]').trigger('click')
    await flushPromises()

    expect(applyMeetingNotesDraft).toHaveBeenCalledTimes(1)
    const [id, body] = applyMeetingNotesDraft.mock.calls[0]!
    expect(id).toBe(5)
    expect(body.cards).toHaveLength(2)
    expect(body.attendees?.[0]).toEqual({ kind: 'user', status: 'present', user_id: 7 })
    expect(router.currentRoute.value.path).toBe('/workspace/projects/142/meeting-notes/21')
  })

  it('keeps Apply disabled without write:meetings', async () => {
    const { wrapper } = await mountAt('/meeting-notes-drafts/5', [])

    expect(wrapper.find('[data-testid="draft-apply"]').attributes('disabled')).toBeDefined()
  })

  it('says so when the draft is gone', async () => {
    getMeetingNotesDraft.mockRejectedValue({ isAxiosError: true, response: { status: 404, data: {} } })

    const { wrapper } = await mountAt('/meeting-notes-drafts/9')

    expect(wrapper.find('[data-testid="draft-not-found"]').exists()).toBe(true)
  })
})
