import { describe, expect, it } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeTestRouter } from '@/test-utils/factories'
import { makeMeeting } from './meetingFixtures'
import MeetingInfoBar from '../components/MeetingInfoBar.vue'

async function mountBar(tags: string[]) {
  const router = makeTestRouter()
  await router.push('/')
  await router.isReady()
  const wrapper = mountWithApp(MeetingInfoBar, {
    props: { meeting: makeMeeting({ tags }) },
    global: { plugins: [router] },
  })
  await flushPromises()
  return wrapper
}

describe('MeetingInfoBar', () => {
  it('shows the tags of the meeting after its other facts', async () => {
    const wrapper = await mountBar(['Milestone', 'Factory acceptance'])

    const tags = wrapper.get('[data-testid="meeting-info-tags"]')
    expect(tags.text()).toContain('Milestone')
    expect(tags.text()).toContain('Factory acceptance')
    const text = wrapper.text()
    expect(text.indexOf('Project 26-0142')).toBeLessThan(text.indexOf('Milestone'))
  })

  it('shows no tag strip for a meeting without tags', async () => {
    const wrapper = await mountBar([])

    expect(wrapper.find('[data-testid="meeting-info-tags"]').exists()).toBe(false)
  })
})
