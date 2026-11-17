import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeUserResponse } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import type { UserResponse } from '@/core/types/userResponse'
import type { UserUpdateRequest } from '@/core/types/userRequest'
import type { UserGroupResponse } from '../../types/userGroup'

const updateUserMock = vi.fn<(id: number, payload: UserUpdateRequest) => Promise<UserResponse>>()

vi.mock('@/core/api/users/getUserDirectory', () => ({
  getUserDirectory: () => Promise.resolve({ items: [], total: 0, limit: 100, skip: 0 }),
}))
vi.mock('@/core/api/users/updateUser', () => ({
  updateUser: (id: number, payload: UserUpdateRequest) => updateUserMock(id, payload),
}))
vi.mock('@/core/api/users/getUserAvatar', () => ({ getUserAvatar: () => Promise.resolve(null) }))
vi.mock('../../api/userPasskeys', () => ({
  fetchUserPasskeys: () => Promise.resolve([]),
  resetUserPasskeys: () => Promise.resolve(0),
}))

const PURCHASING: UserGroupResponse = {
  id: 3,
  public_id: '33333333-3333-3333-3333-333333333333',
  created: '2026-11-01T00:00:00Z',
  changed: null,
  name: 'Purchasing',
  description: '',
  permissions: ['write:orders'],
  member_ids: [7],
  creator_id: 1,
  changed_by_id: null,
  changed_by: null,
}
vi.mock('../../api/userGroups', () => ({
  getUserGroups: () => Promise.resolve([PURCHASING]),
  createUserGroup: () => Promise.reject(new Error('not used')),
  updateUserGroup: () => Promise.reject(new Error('not used')),
  deleteUserGroup: () => Promise.resolve(),
}))

vi.mock('openvue/useconfirm', () => ({ useConfirm: () => ({ require: () => {} }) }))

import UserFormDialog from '../UserFormDialog.vue'

type FormVm = { form: { group_ids: number[]; permissions: string[] } }

async function mountDialog(user: UserResponse, currentUserId = 999) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = makeUserResponse({
    id: currentUserId,
    permissions: ['write:settings'],
  })
  const wrapper = mountWithApp(UserFormDialog, {
    pinia,
    attachTo: document.body,
    props: { visible: false, user },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

function findButton(wrapper: VueWrapper, label: string) {
  return wrapper.findAllComponents({ name: 'Button' }).find((b) => b.props('label') === label)
}

describe('UserFormDialog groups', () => {
  beforeEach(() => {
    updateUserMock.mockReset()
  })

  it('shows a permission of a selected group checked and disabled', async () => {
    const wrapper = await mountDialog(
      makeUserResponse({ id: 7, group_ids: [3], permissions: ['write:orders'] }),
    )

    const inherited = document.querySelector('input[id="perm-write:orders"]') as HTMLInputElement
    expect(inherited.checked).toBe(true)
    expect(inherited.disabled).toBe(true)
    const own = document.querySelector('input[id="perm-write:printers"]') as HTMLInputElement
    expect(own.disabled).toBe(false)

    wrapper.unmount()
  })

  it('offers to drop a direct grant that a group also gives, and saves only direct grants', async () => {
    const user = makeUserResponse({
      id: 7,
      group_ids: [3],
      permissions: ['write:orders', 'write:printers'],
      direct_permissions: ['write:orders', 'write:printers'],
    })
    updateUserMock.mockResolvedValue(user)
    const wrapper = await mountDialog(user)
    const vm = wrapper.vm as unknown as FormVm

    const drop = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.attributes('data-testid') === 'drop-direct-write:orders')
    expect(drop).toBeTruthy()
    await drop!.trigger('click')
    expect(vm.form.permissions).toEqual(['write:printers'])

    await findButton(wrapper, 'Save')!.trigger('click')
    await flushPromises()
    expect(updateUserMock).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ group_ids: [3], permissions: ['write:printers'] }),
    )

    wrapper.unmount()
  })

  it('locks the group picker on the own account', async () => {
    const wrapper = await mountDialog(makeUserResponse({ id: 999 }), 999)

    const picker = wrapper
      .findAllComponents({ name: 'MultiSelect' })
      .find((m) => m.attributes('id') === 'u-groups')
    expect(picker?.props('disabled')).toBe(true)

    wrapper.unmount()
  })
})
