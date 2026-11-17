import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { ConfirmationOptions } from 'openvue/confirmationoptions'
import type { ToastMessageOptions } from 'openvue/toast'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeUserResponse } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { i18n } from '@/core/i18n'
import type { UserResponse } from '@/core/types/userResponse'
import type { UserUpdateRequest } from '@/core/types/userRequest'

const getUsersMock =
  vi.fn<() => Promise<{ items: UserResponse[]; total: number; limit: number; skip: number }>>()
const updateUserMock = vi.fn<(id: number, payload: UserUpdateRequest) => Promise<UserResponse>>()
const deleteCredentialsMock = vi.fn<(id: number) => Promise<void>>()

vi.mock('@/core/api/users/getUserDirectory', () => ({
  getUserDirectory: () => getUsersMock(),
}))
vi.mock('@/core/api/users/updateUser', () => ({
  updateUser: (id: number, payload: UserUpdateRequest) => updateUserMock(id, payload),
}))
vi.mock('../../api/deleteUserTimeTrackingCredentials', () => ({
  deleteUserTimeTrackingCredentials: (id: number) => deleteCredentialsMock(id),
}))

const confirmRequireMock = vi.fn<(options: ConfirmationOptions) => void>()
vi.mock('openvue/useconfirm', () => ({
  useConfirm: () => ({ require: confirmRequireMock }),
}))

const toastAddMock = vi.fn<(options: ToastMessageOptions) => void>()
vi.mock('openvue/usetoast', () => ({
  useToast: () => ({ add: toastAddMock }),
}))

import UserFormDialog from '../UserFormDialog.vue'

const t = i18n.global.t

const NOT_ALLOWED = {
  isAxiosError: true,
  response: {
    status: 409,
    data: { detail: 'Remove the credentials first.', code: 'TimeTrackingCredentialsNotAllowedError' },
  },
}

async function mountDialog(currentUserPermissions: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = makeUserResponse({ id: 999, permissions: currentUserPermissions })

  const wrapper = mountWithApp(UserFormDialog, {
    pinia,
    attachTo: document.body,
    props: { visible: false, user: makeUserResponse({ id: 5 }) },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

function findButton(wrapper: VueWrapper, label: string) {
  return wrapper.findAllComponents({ name: 'Button' }).find((b) => b.props('label') === label)
}

async function saveAsSharedAccount(wrapper: VueWrapper) {
  const vm = wrapper.vm as unknown as { form: { is_shared_account: boolean; member_ids: number[] } }
  vm.form.is_shared_account = true
  await flushPromises()
  vm.form.member_ids = [2]
  await findButton(wrapper, t('common.save'))!.trigger('click')
  await flushPromises()
}

describe('UserFormDialog, time tracking credentials', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getUsersMock.mockResolvedValue({ items: [], total: 0, limit: 100, skip: 0 })
    updateUserMock.mockRejectedValue(NOT_ALLOWED)
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('explains the refusal in a toast and offers removing the credentials', async () => {
    const wrapper = await mountDialog(['write:settings'])

    await saveAsSharedAccount(wrapper)

    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({
        severity: 'error',
        summary: t('settings.users.timeTrackingNotAllowed'),
        detail: t('settings.users.timeTrackingNotAllowedDetail'),
      }),
    )
    const removeButton = findButton(wrapper, t('settings.users.removeTimeTracking'))
    expect(removeButton).toBeDefined()

    await removeButton!.trigger('click')
    expect(confirmRequireMock).toHaveBeenCalledTimes(1)
    expect(deleteCredentialsMock).not.toHaveBeenCalled()

    deleteCredentialsMock.mockResolvedValue()
    await (confirmRequireMock.mock.calls[0]![0].accept as () => Promise<void>)()
    await flushPromises()

    expect(deleteCredentialsMock).toHaveBeenCalledWith(5)
    expect(findButton(wrapper, t('settings.users.removeTimeTracking'))).toBeUndefined()

    wrapper.unmount()
  })

  it('shows the removal disabled with the missing permission without write:settings', async () => {
    const wrapper = await mountDialog(['read:settings'])

    await saveAsSharedAccount(wrapper)

    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({
        detail: t('settings.users.timeTrackingNotAllowedNoPermission'),
      }),
    )
    const removeButton = findButton(wrapper, t('settings.users.removeTimeTracking'))
    expect(removeButton?.attributes('disabled')).toBeDefined()
    const span = removeButton?.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
    expect(span?.$_ptooltipValue).toBe('This needs the permission Write Settings.')

    wrapper.unmount()
  })
})
