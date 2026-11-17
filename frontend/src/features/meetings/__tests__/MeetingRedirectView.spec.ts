import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeTestRouter } from '@/test-utils/factories'
import { makeMeeting } from './meetingFixtures'
import type { MeetingResponse } from '../types/meetingResponse'

const getMeeting = vi.fn<(id: number) => Promise<MeetingResponse>>()
vi.mock('../api/meetingsApi', () => ({ getMeeting: (id: number) => getMeeting(id) }))

import MeetingRedirectView from '../views/MeetingRedirectView.vue'

async function mountAt(path: string) {
  const router = makeTestRouter([{ path: '/meetings/:id(\\d+)', name: 'MeetingRedirect', component: MeetingRedirectView }])
  await router.push(path)
  await router.isReady()
  const wrapper = mountWithApp(MeetingRedirectView, { global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, router }
}

beforeEach(() => {
  getMeeting.mockResolvedValue(makeMeeting())
})

describe('MeetingRedirectView', () => {
  it('replaces the route with the page of the meeting below its project', async () => {
    const { router } = await mountAt('/meetings/21')

    expect(getMeeting).toHaveBeenCalledWith(21)
    expect(router.currentRoute.value.fullPath).toBe('/workspace/projects/142/meeting-notes/21')
  })

  it('opens a meeting of a product below the product and keeps a card anchor', async () => {
    getMeeting.mockResolvedValue(makeMeeting({ id: 19, owner: { kind: 'product', id: 31, number: 'PR-0031', product_id: null } }))

    const { router } = await mountAt('/meetings/19#card-4')

    expect(router.currentRoute.value.fullPath).toBe('/workspace/products/31/meeting-notes/19#card-4')
  })

  it('says so when the meeting cannot be found', async () => {
    getMeeting.mockRejectedValue(new Error('Not found'))

    const { wrapper, router } = await mountAt('/meetings/99')

    expect(wrapper.find('[data-testid="meeting-redirect-failed"]').exists()).toBe(true)
    expect(router.currentRoute.value.fullPath).toBe('/meetings/99')
  })
})
