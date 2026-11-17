import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeUserResponse } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import type { SaveUserGroupRequest, UserGroupResponse } from '../../types/userGroup'

const createUserGroupMock = vi.fn<(payload: SaveUserGroupRequest) => Promise<UserGroupResponse>>()

vi.mock('@/core/api/users/getUserDirectory', () => ({
  getUserDirectory: () =>
    Promise.resolve({
      items: [
        makeUserResponse({ id: 2, full_name: 'Planner' }),
        makeUserResponse({ id: 3, full_name: 'Bot', is_service_account: true }),
        makeUserResponse({ id: 999, full_name: 'Me' }),
      ],
      total: 3,
      limit: 100,
      skip: 0,
    }),
}))
vi.mock('../../api/userGroups', () => ({
  getUserGroups: () => Promise.resolve([]),
  createUserGroup: (payload: SaveUserGroupRequest) => createUserGroupMock(payload),
  updateUserGroup: () => Promise.reject(new Error('not used')),
  deleteUserGroup: () => Promise.resolve(),
}))

import UserGroupFormDialog from '../UserGroupFormDialog.vue'

function group(overrides: Partial<UserGroupResponse> = {}): UserGroupResponse {
  return {
    id: 1,
    public_id: '44444444-4444-4444-4444-444444444444',
    created: '2026-11-01T00:00:00Z',
    changed: null,
    name: 'Planning',
    description: '',
    permissions: ['write:machines'],
    member_ids: [],
    creator_id: 1,
    changed_by_id: null,
    changed_by: null,
    ...overrides,
  }
}

async function mountDialog(props: { group?: UserGroupResponse } = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = makeUserResponse({ id: 999, permissions: ['write:settings'] })
  const wrapper = mountWithApp(UserGroupFormDialog, {
    pinia,
    attachTo: document.body,
    props: { visible: false, ...props },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

function memberPicker(wrapper: VueWrapper) {
  return wrapper.findComponent({ name: 'MultiSelect' })
}

describe('UserGroupFormDialog', () => {
  beforeEach(() => {
    createUserGroupMock.mockReset()
  })

  it('creates a group with its name, permissions and members', async () => {
    createUserGroupMock.mockResolvedValue(group())
    const wrapper = await mountDialog()

    const name = document.querySelector('input[id="g-name"]') as HTMLInputElement
    name.value = '  Planning  '
    name.dispatchEvent(new Event('input'))
    const perm = document.querySelector('input[id="g-perm-write:machines"]') as HTMLInputElement
    perm.checked = true
    perm.dispatchEvent(new Event('change'))
    await memberPicker(wrapper).vm.$emit('update:modelValue', [2])
    await flushPromises()

    const save = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.attributes('data-testid') === 'user-group-save')
    await save!.trigger('click')
    await flushPromises()

    expect(createUserGroupMock).toHaveBeenCalledWith({
      name: 'Planning',
      description: '',
      permissions: ['write:machines'],
      member_ids: [2],
    })

    wrapper.unmount()
  })

  it('offers no service account and keeps the own account unselectable', async () => {
    const wrapper = await mountDialog()

    const options = memberPicker(wrapper).props('options') as { id: number; disabled: boolean }[]
    expect(options.map((o) => o.id)).toEqual([2, 999])
    expect(options.find((o) => o.id === 999)?.disabled).toBe(true)

    wrapper.unmount()
  })

  it('locks the permissions of a group the current user belongs to', async () => {
    const wrapper = await mountDialog({ group: group({ member_ids: [999] }) })

    const perm = document.querySelector('input[id="g-perm-write:machines"]') as HTMLInputElement
    expect(perm.checked).toBe(true)
    expect(perm.disabled).toBe(true)

    wrapper.unmount()
  })
})
