import { describe, it, expect } from 'vitest'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeMeeting } from './meetingFixtures'
import MeetingInfoCard from '../components/MeetingInfoCard.vue'

describe('MeetingInfoCard', () => {
  it('lists every attendee with the e-mail address and a status tag', () => {
    const meeting = makeMeeting()
    meeting.attendees.push({
      id: 6,
      public_id: '00000000-0000-0000-0000-000000000006',
      kind: 'guest',
      status: 'excused',
      position: 1,
      user: null,
      contact_id: null,
      name: 'Paul Lorem',
      email: 'p.lorem@example.com',
      anonymised: false,
    })
    const wrapper = mountWithApp(MeetingInfoCard, {
      props: { meeting },
      global: { directives: { tooltip: Tooltip } },
    })

    const rows = wrapper.findAll('[data-testid="meeting-info-attendee"]')
    expect(rows.map((row) => row.text())).toEqual([
      expect.stringContaining('anna.generic@example.com'),
      expect.stringContaining('p.lorem@example.com'),
    ])
    const tags = wrapper.findAll('[data-testid="meeting-info-attendee-status"]').map((tag) => tag.text())
    expect(tags).toEqual(['Present', 'Excused'])
    expect(rows[0]?.find('.user-avatar-preview-bubble').exists()).toBe(true)
  })

  it('shows the next meeting only when one is set', () => {
    const mount = (overrides: Parameters<typeof makeMeeting>[0]) =>
      mountWithApp(MeetingInfoCard, {
        props: { meeting: makeMeeting(overrides) },
        global: { directives: { tooltip: Tooltip } },
      })

    expect(mount({}).find('[data-testid="meeting-info-next"]').exists()).toBe(false)
    const next = mount({ next_meeting_date: '2026-11-20', next_meeting_time: '09:00:00', next_meeting_location: 'Teams' })
    expect(next.get('[data-testid="meeting-info-next"]').text()).toContain('Teams')
  })
})
