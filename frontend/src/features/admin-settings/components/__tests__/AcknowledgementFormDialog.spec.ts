import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, DOMWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { i18n } from '@/core/i18n'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeUserResponse } from '@/test-utils/factories'
import type { PageResponse } from '@/core/api/types'
import type { UserFilterDto } from '@/core/types/userRequest'
import type { UserResponse } from '@/core/types/userResponse'
import type { Acknowledgement, CreateAcknowledgementCommand } from '../../types/acknowledgementTypes'

const getUsersMock = vi.fn<(params?: UserFilterDto) => Promise<PageResponse<UserResponse>>>()
const createAcknowledgementMock =
  vi.fn<(cmd: CreateAcknowledgementCommand) => Promise<Acknowledgement>>()

vi.mock('@/core/api/users/getUsers', () => ({
  getUsers: (params?: UserFilterDto) => getUsersMock(params),
}))
// The user pickers read the directory, user administration the full list.
vi.mock('@/core/api/users/getUserDirectory', () => ({
  getUserDirectory: (params?: UserFilterDto) => getUsersMock(params),
}))
vi.mock('../../api/createAcknowledgement', () => ({
  createAcknowledgement: (cmd: CreateAcknowledgementCommand) => createAcknowledgementMock(cmd),
}))

import AcknowledgementFormDialog from '../AcknowledgementFormDialog.vue'

function page(items: UserResponse[], total = items.length): PageResponse<UserResponse> {
  return { items, total, limit: 500, skip: 0 }
}

function makeAcknowledgement(overrides: Partial<Acknowledgement> = {}): Acknowledgement {
  return {
    id: 1,
    public_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    text: 'Please confirm this.',
    severity: 'info',
    enabled: true,
    show_when: 'immediately',
    created_at: '2026-01-01T00:00:00Z',
    created_by_username: 'admin',
    recipients_total: 2,
    recipients_acknowledged: 0,
    ...overrides,
  }
}

function mountDialog() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mountWithApp(AcknowledgementFormDialog, {
    pinia,
    attachTo: document.body,
    props: { visible: false },
  })
}

function saveButton() {
  return Array.from(document.body.querySelectorAll('.dialog-footer button')).find((button) => button.textContent?.includes(i18n.global.t('common.save') as string))
}

describe('AcknowledgementFormDialog', () => {
  beforeEach(() => {
    getUsersMock.mockReset()
    createAcknowledgementMock.mockReset()
    document.body.innerHTML = ''
  })

  it('asks the users list to leave out API-key service accounts', async () => {
    getUsersMock.mockResolvedValue(page([makeUserResponse({ id: 1 })]))
    const wrapper = mountDialog()

    await wrapper.setProps({ visible: true })
    await flushPromises()

    expect(getUsersMock).toHaveBeenCalledWith(
      expect.objectContaining({ is_active: true, is_service_account: false }),
    )

    wrapper.unmount()
  })

  it('preselects every active user, including shared accounts, when opened', async () => {
    getUsersMock.mockResolvedValue(
      page([
        makeUserResponse({ id: 1, is_shared_account: false }),
        makeUserResponse({ id: 2, is_shared_account: true, username: 'shared-scanner' }),
      ]),
    )
    const wrapper = mountDialog()

    await wrapper.setProps({ visible: true })
    await flushPromises()

    expect(getUsersMock).toHaveBeenCalledWith(
      expect.objectContaining({ is_active: true, limit: 500 }),
    )
    const multiSelect = wrapper.findComponent({ name: 'MultiSelect' })
    expect(multiSelect.props('modelValue')).toEqual([1, 2])

    wrapper.unmount()
  })

  it('pages through the full user list rather than truncating at the first page', async () => {
    getUsersMock
      .mockResolvedValueOnce(page([makeUserResponse({ id: 1 })], 3))
      .mockResolvedValueOnce(page([makeUserResponse({ id: 2 }), makeUserResponse({ id: 3 })], 3))
    const wrapper = mountDialog()

    await wrapper.setProps({ visible: true })
    await flushPromises()

    expect(getUsersMock).toHaveBeenCalledTimes(2)
    const multiSelect = wrapper.findComponent({ name: 'MultiSelect' })
    expect(multiSelect.props('modelValue')).toEqual([1, 2, 3])

    wrapper.unmount()
  })

  it('disables Save while the text is blank', async () => {
    getUsersMock.mockResolvedValue(page([makeUserResponse({ id: 1 })]))
    const wrapper = mountDialog()

    await wrapper.setProps({ visible: true })
    await flushPromises()

    const button = saveButton()
    expect(button).toBeDefined()
    expect(button!.hasAttribute('disabled')).toBe(true)

    wrapper.unmount()
  })

  it('POSTs the composed command, toasts, and closes on success', async () => {
    getUsersMock.mockResolvedValue(page([makeUserResponse({ id: 1 }), makeUserResponse({ id: 2 })]))
    createAcknowledgementMock.mockResolvedValue(makeAcknowledgement())
    const wrapper = mountDialog()

    await wrapper.setProps({ visible: true })
    await flushPromises()

    await wrapper.findComponent({ name: 'Textarea' }).setValue('Please confirm this.')
    await flushPromises()

    const button = saveButton()
    expect(button!.hasAttribute('disabled')).toBe(false)
    await new DOMWrapper(button!).trigger('click')
    await flushPromises()

    expect(createAcknowledgementMock).toHaveBeenCalledWith({
      text: 'Please confirm this.',
      severity: 'info',
      enabled: true,
      show_when: 'immediately',
      recipient_ids: [1, 2],
    })
    expect(wrapper.emitted('saved')).toBeTruthy()
    const updateVisibleEvents = wrapper.emitted('update:visible')
    expect(updateVisibleEvents?.at(-1)).toEqual([false])

    wrapper.unmount()
  })
})
