import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import type { ConfirmationOptions } from 'openvue/confirmationoptions'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeUserResponse } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useUserManagementStore } from '../../stores/userManagementStore'
import type { UserResponse } from '@/core/types/userResponse'

const getUsersMock =
  vi.fn<
    (params?: { skip?: number; limit?: number }) => Promise<{
      items: UserResponse[]
      total: number
      limit: number
      skip: number
    }>
  >()

vi.mock('@/core/api/users/getUsers', () => ({
  getUsers: (params?: { skip?: number; limit?: number }) => getUsersMock(params),
}))
// The user pickers read the directory, user administration the full list.
vi.mock('@/core/api/users/getUserDirectory', () => ({
  getUserDirectory: (params?: { skip?: number; limit?: number }) => getUsersMock(params),
}))

// Opening UserFormDialog loads the edited user's passkeys. Unmocked, the
// request reaches whatever answers on the API URL, and a 401 from a running
// dev backend expires the session of the next test's current user.
vi.mock('../../api/userPasskeys', () => ({
  fetchUserPasskeys: () => Promise.resolve([]),
  resetUserPasskeys: () => Promise.resolve(0),
}))

// The table itself renders a terminate-session action wired to useConfirm();
// the confirm flow isn't this spec's concern (UserFormDialog.spec.ts and
// UserManagementControls.spec.ts already cover that pattern), so it's
// stubbed out rather than requiring a real <ConfirmDialog/> to mount too,
// same technique as OrdersTable.spec.ts.
const confirmRequireMock = vi.fn<(option: ConfirmationOptions) => void>()
vi.mock('openvue/useconfirm', () => ({
  useConfirm: () => ({ require: confirmRequireMock }),
}))

// The users table and dialog load the groups. Unmocked, that request reaches
// whatever answers on the API URL, like the other requests mocked here.
vi.mock('@/features/users/api/userGroups', () => ({
  getUserGroups: () => Promise.resolve([]),
  createUserGroup: () => Promise.reject(new Error('not used')),
  updateUserGroup: () => Promise.reject(new Error('not used')),
  deleteUserGroup: () => Promise.resolve(),
}))

import UserManagementTable from '../UserManagementTable.vue'

function makeCurrentUser(permissions: string[]): UserResponse {
  return makeUserResponse({ id: 999, permissions })
}

function findButton(wrapper: VueWrapper, icon: string) {
  return wrapper.findAllComponents({ name: 'Button' }).find((b) => b.props('icon') === icon)
}

async function mountTable(users: UserResponse[], currentUserPermissions: string[] = []) {
  getUsersMock.mockResolvedValue({ items: users, total: users.length, limit: 100, skip: 0 })

  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = makeCurrentUser(currentUserPermissions)

  const wrapper = mountWithApp(UserManagementTable, { pinia, attachTo: document.body })
  await flushPromises()
  await flushPromises()
  return wrapper
}

describe('UserManagementTable', () => {
  beforeEach(() => {
    getUsersMock.mockReset()
  })

  it('hides the actions column by default and shows it once store.showActions flips on', async () => {
    const wrapper = await mountTable([makeUserResponse()], ['write:settings'])

    expect(findButton(wrapper, 'mdi mdi-pencil')).toBeUndefined()

    useUserManagementStore().showActions = true
    await flushPromises()

    expect(findButton(wrapper, 'mdi mdi-pencil')).toBeTruthy()

    wrapper.unmount()
  })

  it('disables the edit and terminate-session actions when the current user lacks write:settings', async () => {
    const wrapper = await mountTable(
      [makeUserResponse({ last_logged_in: '2026-08-01T00:00:00Z' })],
      [],
    )
    useUserManagementStore().showActions = true
    await flushPromises()

    expect(findButton(wrapper, 'mdi mdi-pencil')!.attributes('disabled')).toBeDefined()
    expect(findButton(wrapper, 'mdi mdi-logout-variant')!.attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  it('disables terminate-session for a user who has never logged in, even with write:settings', async () => {
    const wrapper = await mountTable(
      [makeUserResponse({ last_logged_in: null })],
      ['write:settings'],
    )
    useUserManagementStore().showActions = true
    await flushPromises()

    expect(findButton(wrapper, 'mdi mdi-pencil')!.attributes('disabled')).toBeUndefined()
    expect(findButton(wrapper, 'mdi mdi-logout-variant')!.attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  it('opens UserFormDialog pre-populated with the row when Edit is clicked', async () => {
    const target = makeUserResponse({ id: 7, username: 'target', full_name: 'Target User' })
    const wrapper = await mountTable([target], ['write:settings'])
    useUserManagementStore().showActions = true
    await flushPromises()

    await findButton(wrapper, 'mdi mdi-pencil')!.trigger('click')

    const dialog = wrapper.findComponent({ name: 'UserFormDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect((dialog.props('user') as UserResponse).id).toBe(7)

    wrapper.unmount()
  })

  it('shows up to 4 permission tags plus a "+N more" tag for the remainder', async () => {
    const perms = [
      'write:orders',
      'manage:orders',
      'write:lots',
      'manage:lots',
      'write:machines',
      'manage:production_orders',
    ]
    const wrapper = await mountTable([makeUserResponse({ permissions: perms })])

    const tags = wrapper.findAllComponents({ name: 'Tag' })
    const moreTag = tags.find((t) => (t.props('value') as string)?.includes('more'))
    expect(moreTag?.props('value')).toBe('+2 more')

    wrapper.unmount()
  })

  it("shows a single 'Full Control' tag for the system user instead of individual permission tags", async () => {
    const wrapper = await mountTable([
      makeUserResponse({ is_systemuser: true, permissions: ['write:orders'] }),
    ])

    const tags = wrapper.findAllComponents({ name: 'Tag' })
    const values = tags.map((t) => t.props('value'))
    expect(values).toContain('Full Control')
    expect(values).not.toContain('Write Orders')

    wrapper.unmount()
  })

  it('shows "No members assigned" for a shared account with an empty member list', async () => {
    const wrapper = await mountTable([
      makeUserResponse({ is_shared_account: true, member_ids: [] }),
    ])

    expect(wrapper.text()).toContain('No members assigned')

    wrapper.unmount()
  })

  it('offers Edit and Terminate Session from the row context menu without enabling the actions column', async () => {
    const target = makeUserResponse({
      id: 7,
      username: 'target',
      last_logged_in: '2026-08-01T00:00:00Z',
    })
    const wrapper = await mountTable([target], ['write:settings'])

    await wrapper.find('tbody tr').trigger('contextmenu')
    await flushPromises()

    const contextMenu = wrapper.findComponent({ name: 'ContextMenu' })
    const items = contextMenu.props('model') as Array<{
      label?: string
      disabled?: boolean
      command?: () => void
    }>
    const editItem = items.find((i) => i.label === 'Edit User')
    const terminateItem = items.find((i) => i.label === 'Terminate Session')
    expect(editItem?.disabled).toBe(false)
    expect(terminateItem?.disabled).toBe(false)

    editItem!.command!()
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'UserFormDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect((dialog.props('user') as UserResponse).id).toBe(7)

    terminateItem!.command!()
    expect(confirmRequireMock).toHaveBeenCalled()

    wrapper.unmount()
  })

  it('disables the Edit and Terminate Session context-menu items without write:settings or without a login', async () => {
    const wrapper = await mountTable([makeUserResponse({ last_logged_in: null })], [])

    await wrapper.find('tbody tr').trigger('contextmenu')
    await flushPromises()

    const items = wrapper.findComponent({ name: 'ContextMenu' }).props('model') as Array<{
      label?: string
      disabled?: boolean
    }>
    expect(items.find((i) => i.label === 'Edit User')?.disabled).toBe(true)
    expect(items.find((i) => i.label === 'Terminate Session')?.disabled).toBe(true)
    expect(items.find((i) => i.label === 'Copy UUID')?.disabled).toBeUndefined()

    wrapper.unmount()
  })

  it('copies the row public_id to the clipboard from the "Copy UUID" context-menu action', async () => {
    const writeText = vi.fn<(text: string) => Promise<void>>().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })

    const target = makeUserResponse({ public_id: '22222222-2222-2222-2222-222222222222' })
    const wrapper = await mountTable([target])

    const row = wrapper.find('tbody tr')
    await row.trigger('contextmenu')
    await flushPromises()

    const contextMenu = wrapper.findComponent({ name: 'ContextMenu' })
    const items = contextMenu.props('model') as Array<{ label?: string; command?: () => void }>
    const copyItem = items.find((i) => i.label === 'Copy UUID')
    expect(copyItem).toBeDefined()

    copyItem!.command!()
    await flushPromises()

    expect(writeText).toHaveBeenCalledWith('22222222-2222-2222-2222-222222222222')

    wrapper.unmount()
  })

  // Users use the same server-side `lazy` pagination as
  // suppliers/customers: `userManagementStore.total` backs `totalRecords`, and
  // paging emits skip/limit through userManagementStore.refreshTable() rather than
  // loading the whole list once.
  it('is a lazy DataTable whose totalRecords comes from the server total', async () => {
    getUsersMock.mockResolvedValue({ items: [makeUserResponse()], total: 120, limit: 25, skip: 0 })

    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = makeCurrentUser([])

    const wrapper = mountWithApp(UserManagementTable, { pinia, attachTo: document.body })
    await flushPromises()
    await flushPromises()

    const table = wrapper.findComponent({ name: 'DataTable' })
    expect(table.props('lazy')).toBe(true)
    expect(table.props('totalRecords')).toBe(120)

    wrapper.unmount()
  })

  it('requests the next page with the correct skip/limit on @page', async () => {
    getUsersMock.mockResolvedValue({ items: [makeUserResponse()], total: 60, limit: 25, skip: 0 })

    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = makeCurrentUser([])

    const wrapper = mountWithApp(UserManagementTable, { pinia, attachTo: document.body })
    await flushPromises()
    await flushPromises()

    getUsersMock.mockClear()
    getUsersMock.mockResolvedValue({
      items: [makeUserResponse({ id: 2, username: 'page2' })],
      total: 60,
      limit: 25,
      skip: 25,
    })

    const next = wrapper.find('[aria-label="Next Page"]')
    await next.trigger('click')
    await flushPromises()

    expect(getUsersMock).toHaveBeenCalledWith(expect.objectContaining({ skip: 25, limit: 25 }))

    wrapper.unmount()
  })

  it('bumps the table refetch via refreshTrigger without touching the picker-facing users list', async () => {
    getUsersMock.mockResolvedValue({ items: [makeUserResponse()], total: 1, limit: 25, skip: 0 })

    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = makeCurrentUser([])

    const wrapper = mountWithApp(UserManagementTable, { pinia, attachTo: document.body })
    await flushPromises()
    await flushPromises()

    getUsersMock.mockClear()
    useUserManagementStore().triggerRefresh()
    await flushPromises()

    expect(getUsersMock).toHaveBeenCalledTimes(1)
    expect(getUsersMock).toHaveBeenCalledWith(expect.objectContaining({ skip: 0, limit: 25 }))

    wrapper.unmount()
  })

  // Under `lazy` OpenVue only emits @sort and fetches nothing itself, so the
  // table must wire the event or a header click would only toggle the icon.
  it('fetches with order_by/order_dir and resets to page 1 on a header sort click', async () => {
    getUsersMock.mockResolvedValue({ items: [makeUserResponse()], total: 60, limit: 25, skip: 0 })

    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = makeCurrentUser([])

    const wrapper = mountWithApp(UserManagementTable, { pinia, attachTo: document.body })
    await flushPromises()
    await flushPromises()

    // Move off page 1 first, so the sort click's reset is observable.
    getUsersMock.mockClear()
    getUsersMock.mockResolvedValue({ items: [makeUserResponse()], total: 60, limit: 25, skip: 25 })
    await wrapper.find('[aria-label="Next Page"]').trigger('click')
    await flushPromises()

    getUsersMock.mockClear()
    getUsersMock.mockResolvedValue({ items: [makeUserResponse()], total: 60, limit: 25, skip: 0 })
    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('sort', { sortField: 'username', sortOrder: 1 })
    await flushPromises()

    expect(getUsersMock).toHaveBeenCalledWith(
      expect.objectContaining({ skip: 0, limit: 25, order_by: 'username', order_dir: 'asc' }),
    )

    wrapper.unmount()
  })

  it('does not mark the auth provider column sortable (not in the backend allow-list)', async () => {
    const wrapper = await mountTable([makeUserResponse()])

    const column = wrapper
      .findAllComponents({ name: 'Column' })
      .find((c) => c.props('field') === 'auth_provider')
    expect(column?.props('sortable')).toBeFalsy()

    wrapper.unmount()
  })
})
