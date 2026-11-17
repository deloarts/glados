import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeMeeting } from './meetingFixtures'
import type { MeetingFileResponse } from '../types/meetingResponse'

const renameMeetingFile = vi.fn<(meetingId: number, fileId: number, name: string) => Promise<MeetingFileResponse>>()
vi.mock('../api/meetingsApi', () => ({
  deleteMeetingFile: vi.fn<() => Promise<void>>(),
  fetchMeetingFileBlob: vi.fn<() => Promise<Blob>>(),
  uploadMeetingFile: vi.fn<() => Promise<void>>(),
  renameMeetingFile: (meetingId: number, fileId: number, name: string) => renameMeetingFile(meetingId, fileId, name),
}))

import MeetingDocumentsCard from '../components/MeetingDocumentsCard.vue'

const FILE = {
  id: 4,
  public_id: '00000000-0000-0000-0000-000000000004',
  meeting_id: 21,
  card_id: null,
  category: 'pdf',
  file_name: 'Offer.pdf',
  content_type: 'application/pdf',
  size_bytes: 2048,
  storage_path: 'meetings/21/pdf/offer.pdf',
  created: '2026-11-06T08:00:00Z',
  creator: null,
} as unknown as MeetingFileResponse

describe('MeetingDocumentsCard', () => {
  it('renames a file in place and keeps its extension', async () => {
    renameMeetingFile.mockResolvedValue({ ...FILE, file_name: 'Offer v2.pdf' })
    const wrapper = mountWithApp(MeetingDocumentsCard, {
      props: { meeting: makeMeeting({ files: [FILE] }), canWrite: true, writeBlocked: '' },
      global: { directives: { tooltip: Tooltip } },
    })

    await wrapper.get('[data-testid="meeting-file-rename-4"]').trigger('click')
    await wrapper.get('[data-testid="meeting-file-rename-input"]').setValue('Offer v2')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(renameMeetingFile).toHaveBeenCalledWith(21, 4, 'Offer v2.pdf')
    expect(wrapper.emitted('changed')).toHaveLength(1)
  })
})
