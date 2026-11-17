import { describe, it, expect } from 'vitest'

import NotificationPanel from '../NotificationPanel.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'
import type { NotificationResponse } from '../../types/notificationTypes'

function makeNotification(overrides: Partial<NotificationResponse> = {}): NotificationResponse {
  return {
    id: 1,
    public_id: '00000000-0000-0000-0000-000000000001',
    type: 'demand',
    title: 'Title',
    message: 'Message',
    is_read: false,
    created_at: '2026-08-20T10:00:00Z',
    demand_item_id: null,
    order_id: null,
    project_id: null,
    product_id: null,
    meeting_id: null,
    ...overrides,
  }
}

function mountPanel(items: NotificationResponse[], loading = false) {
  return mountWithApp(NotificationPanel, {
    props: { items, loading },
  })
}

// NotificationPanel takes items/loading props and emits mark-read/
// mark-all-read; the consumer (AppHeader, in `app/`) owns the store and does
// the wiring. These specs drive that contract in isolation, with no store
// involved.
describe('NotificationPanel', () => {
  it('shows a loading state before anything has arrived', () => {
    const wrapper = mountPanel([], true)

    expect(wrapper.find('[data-testid="notification-loading-icon"]').exists()).toBe(true)
  })

  it('shows the empty state once loaded with nothing unread', () => {
    const wrapper = mountPanel([], false)

    expect(wrapper.find('.panel-empty-icon').exists()).toBe(true)
    expect(wrapper.find('[data-testid="notification-loading-icon"]').exists()).toBe(false)
  })

  it('shows the empty state, not a spinner, for a background refresh once something has already loaded', () => {
    // loading=true but items is non-empty and already all-read, which is a poll tick
    // refreshing in the background, not the first load. items is the total
    // notification count, so the two-branch check tells this apart from
    // "nothing fetched yet" without a separate "has loaded" signal.
    const wrapper = mountPanel([makeNotification({ is_read: true })], true)

    expect(wrapper.find('[data-testid="notification-loading-icon"]').exists()).toBe(false)
    expect(wrapper.find('.panel-empty-icon').exists()).toBe(true)
  })

  it('lists only the unread notifications', () => {
    const wrapper = mountPanel([
      makeNotification({ id: 1, is_read: true, title: 'Read one' }),
      makeNotification({ id: 2, is_read: false, title: 'Unread one' }),
    ])

    const items = wrapper.findAll('.notification-item')
    expect(items).toHaveLength(1)
    expect(wrapper.text()).toContain('Unread one')
    expect(wrapper.text()).not.toContain('Read one')
  })

  it('emits mark-read with the notification id when an item is clicked', async () => {
    const wrapper = mountPanel([makeNotification({ id: 42 })])

    await wrapper.find('.notification-item-btn').trigger('click')

    expect(wrapper.emitted('mark-read')).toEqual([[42]])
  })

  it('opens the meeting a notification links to', async () => {
    const wrapper = mountPanel([makeNotification({ id: 7, meeting_id: 31 })])

    await wrapper.find('.notification-item-btn').trigger('click')

    expect(wrapper.emitted('mark-read')).toEqual([[7]])
    expect(wrapper.emitted('open')).toEqual([['/meetings/31']])
  })

  it('opens nothing for a notification without a meeting', async () => {
    const wrapper = mountPanel([makeNotification({ id: 8 })])

    await wrapper.find('.notification-item-btn').trigger('click')

    expect(wrapper.emitted('open')).toBeUndefined()
  })

  it('shows the mark-all button only when something is unread, and emits on click', async () => {
    const readOnly = mountPanel([makeNotification({ is_read: true })])
    expect(readOnly.find('.mark-all-btn').exists()).toBe(false)

    const wrapper = mountPanel([makeNotification({ is_read: false })])
    expect(wrapper.find('.mark-all-btn').exists()).toBe(true)

    await wrapper.find('.mark-all-btn').trigger('click')

    expect(wrapper.emitted('mark-all-read')).toHaveLength(1)
  })
})
