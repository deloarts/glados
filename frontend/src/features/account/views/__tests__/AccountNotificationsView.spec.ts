import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'

import type { NotificationResponse } from '@/features/notifications'

const getNotificationsMock = vi.fn<() => Promise<NotificationResponse[]>>()
const markAllNotificationsReadMock = vi.fn<() => Promise<void>>()
const markNotificationReadMock = vi.fn<(id: number) => Promise<void>>()

vi.mock('@/features/notifications/api/getNotifications', () => ({
  getNotifications: () => getNotificationsMock(),
}))
vi.mock('@/features/notifications/api/markAllNotificationsRead', () => ({
  markAllNotificationsRead: () => markAllNotificationsReadMock(),
}))
vi.mock('@/features/notifications/api/markNotificationRead', () => ({
  markNotificationRead: (id: number) => markNotificationReadMock(id),
}))

import AccountNotificationsView from '../AccountNotificationsView.vue'

const t = i18n.global.t

function makeNotification(overrides: Partial<NotificationResponse> = {}): NotificationResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    type: 'demand_fulfilled',
    title: 'Demand fulfilled',
    message: 'Your demand has been fulfilled.',
    is_read: false,
    created_at: '2026-09-01T10:00:00Z',
    demand_item_id: null,
    order_id: null,
    project_id: null,
    product_id: null,
    meeting_id: null,
    ...overrides,
  }
}

async function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const wrapper = mountWithApp(AccountNotificationsView, { pinia })
  await flushPromises()
  return wrapper
}

describe('AccountNotificationsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getNotificationsMock.mockReset()
    markAllNotificationsReadMock.mockReset()
    markNotificationReadMock.mockReset()
    getNotificationsMock.mockResolvedValue([])
    markAllNotificationsReadMock.mockResolvedValue(undefined)
    markNotificationReadMock.mockResolvedValue(undefined)
  })

  it('fetches notifications on mount with no arguments', async () => {
    const wrapper = await mountView()

    expect(getNotificationsMock).toHaveBeenCalledTimes(1)

    wrapper.unmount()
  })

  it('shows the empty state when there are no notifications', async () => {
    const wrapper = await mountView()

    expect(wrapper.text()).toContain(t('notifications.empty'))
    expect(wrapper.find('.notification-list').exists()).toBe(false)

    wrapper.unmount()
  })

  it('lists fetched notifications and marks the "mark all read" button enabled only while unread ones exist', async () => {
    getNotificationsMock.mockResolvedValue([
      makeNotification({ id: 1, title: 'First', is_read: false }),
      makeNotification({ id: 2, title: 'Second', is_read: true }),
    ])
    const wrapper = await mountView()

    const items = wrapper.findAll('.notification-item')
    expect(items).toHaveLength(2)
    expect(items[0]?.text()).toContain('First')
    expect(items[0]?.classes()).toContain('unread')
    expect(items[1]?.classes()).not.toContain('unread')

    const markAllButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === t('notifications.markAllRead'))!
    expect(markAllButton.attributes('disabled')).toBeUndefined()

    wrapper.unmount()
  })

  it('disables "mark all read" once every notification is already read', async () => {
    getNotificationsMock.mockResolvedValue([makeNotification({ is_read: true })])
    const wrapper = await mountView()

    const markAllButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === t('notifications.markAllRead'))!
    expect(markAllButton.attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  it('marks an unread notification read when clicked, calling the API with its id', async () => {
    getNotificationsMock.mockResolvedValue([makeNotification({ id: 42, is_read: false })])
    const wrapper = await mountView()

    await wrapper.find('.notification-item-btn').trigger('click')
    await flushPromises()

    expect(markNotificationReadMock).toHaveBeenCalledWith(42)
    expect(wrapper.find('.notification-item')?.classes()).not.toContain('unread')

    wrapper.unmount()
  })

  it('marks every notification read via the toolbar button', async () => {
    getNotificationsMock.mockResolvedValue([
      makeNotification({ id: 1, is_read: false }),
      makeNotification({ id: 2, is_read: false }),
    ])
    const wrapper = await mountView()

    const markAllButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === t('notifications.markAllRead'))!
    await markAllButton.trigger('click')
    await flushPromises()

    expect(markAllNotificationsReadMock).toHaveBeenCalledTimes(1)
    expect(wrapper.findAll('.notification-item.unread')).toHaveLength(0)

    wrapper.unmount()
  })

  it('narrows the list to the picked date range and shows the filtered-empty message when nothing matches', async () => {
    getNotificationsMock.mockResolvedValue([
      makeNotification({ id: 1, title: 'Old one', created_at: '2020-01-01T10:00:00Z' }),
    ])
    const wrapper = await mountView()

    const datePicker = wrapper.findComponent({ name: 'DatePicker' })
    await datePicker.vm.$emit('update:modelValue', [new Date(2026, 0, 1), new Date(2026, 0, 2)])
    await flushPromises()

    expect(wrapper.find('.notification-list').exists()).toBe(false)
    expect(wrapper.text()).toContain(t('notifications.filters.empty'))

    const viewsBar = wrapper.findComponent({ name: 'ViewsBar' })
    expect(viewsBar.props('hasActiveFilters')).toBe(true)

    await viewsBar.vm.$emit('clear')
    await flushPromises()

    expect(wrapper.find('.notification-item').exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'ViewsBar' }).props('hasActiveFilters')).toBe(false)

    wrapper.unmount()
  })
})
