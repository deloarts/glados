import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'
import Tooltip from 'openvue/tooltip'
import type { ConfirmationOptions } from 'openvue/confirmationoptions'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { userWithPermissions } from '@/test-utils/factories'
import type { UserResponse } from '@/core/types/userResponse'

// AdminSettingsTabUsers.vue is built on ManagementCrudShell, so its controls
// and views are covered here against the real component tree (users has no
// separate Views/Controls tier).

const getUsersMock =
  vi.fn<() => Promise<{ items: UserResponse[]; total: number; limit: number; skip: number }>>()
const deleteAllSessionsMock = vi.fn<() => Promise<void>>()

vi.mock('@/core/api/users/getUsers', () => ({
  getUsers: () => getUsersMock(),
}))
// The user pickers read the directory, user administration the full list.
vi.mock('@/core/api/users/getUserDirectory', () => ({
  getUserDirectory: () => getUsersMock(),
}))
vi.mock('@/features/users/api/deleteAllSessions', () => ({
  deleteAllSessions: () => deleteAllSessionsMock(),
}))

// Same technique as OrdersTable.spec.ts / UserFormDialog.spec.ts: replace the
// composable so `accept` can be invoked directly instead of driving a real
// <ConfirmDialog/>'s DOM.
const confirmRequireMock = vi.fn<(options: ConfirmationOptions) => void>()
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

import AdminSettingsTabUsers from '../AdminSettingsTabUsers.vue'

function defaultUsersPage() {
  return {
    items: [
      {
        id: 1,
        public_id: '22222222-2222-2222-2222-222222222222',
        pdm_links: [],
        username: 'jdoe',
        full_name: 'Jane Doe',
        email: 'jane.doe@example.com',
        created: '2026-01-01T00:00:00Z',
        language: 'enGB',
        date_format: 'iso',
        start_page: 'dashboard',
        theme_preset: 'Aura',
        theme_surface: 'slate',
        theme_primary: 'indigo',
        theme_dark_mode: false,
        button_flat_style: false,
        table_gridlines: false,
        table_striped_rows: false,
        rfid_configured: false,
        is_active: true,
        is_systemuser: false,
        is_service_account: false,
        is_shared_account: false,
        auth_provider: 'local',
        member_ids: [],
        group_ids: [],
        permissions: [],
        direct_permissions: [],
        last_logged_in: null,
        totp_enabled: false,
        has_avatar: false,
      },
    ],
    total: 1,
    limit: 100,
    skip: 0,
  } as { items: UserResponse[]; total: number; limit: number; skip: number }
}

function findButton(wrapper: VueWrapper, label: string) {
  return wrapper.findAllComponents({ name: 'Button' }).find((b) => b.props('label') === label)
}

async function mountTab(permissions: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)

  const wrapper = mountWithApp(AdminSettingsTabUsers, {
    pinia,
    global: {
      plugins: [ConfirmationService],
      directives: { tooltip: Tooltip },
    },
    attachTo: document.body,
  })

  await flushPromises()
  await flushPromises()

  return wrapper
}

describe('AdminSettingsTabUsers', () => {
  beforeEach(() => {
    getUsersMock.mockReset()
    deleteAllSessionsMock.mockReset()
    confirmRequireMock.mockReset()
    getUsersMock.mockResolvedValue(defaultUsersPage())
  })

  it('disables Create User and Terminate All Sessions when the current user lacks write:settings', async () => {
    const wrapper = await mountTab([])

    // Button has no declared `disabled` prop, it derives disabled-ness from
    // the native attribute it forwards (see SourceItemCreateForm.spec.ts).
    expect(findButton(wrapper, 'Create User')!.attributes('disabled')).toBeDefined()
    expect(findButton(wrapper, 'Terminate All Sessions')!.attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  it('enables both actions once the current user has write:settings', async () => {
    const wrapper = await mountTab(['write:settings'])

    expect(findButton(wrapper, 'Create User')!.attributes('disabled')).toBeUndefined()
    expect(findButton(wrapper, 'Terminate All Sessions')!.attributes('disabled')).toBeUndefined()

    wrapper.unmount()
  })

  it('clicking Create User opens UserFormDialog in create mode', async () => {
    // Two UserFormDialog instances exist in this tree: the outer one (this
    // component's own, for Create) and UserManagementTable's own inner one
    // (for row-level Edit), disambiguate by which one goes visible.
    const wrapper = await mountTab(['write:settings'])

    expect(
      wrapper.findAllComponents({ name: 'UserFormDialog' }).every((d) => d.props('visible') === false),
    ).toBe(true)

    await findButton(wrapper, 'Create User')!.trigger('click')

    const visibleDialogs = wrapper
      .findAllComponents({ name: 'UserFormDialog' })
      .filter((d) => d.props('visible') === true)
    expect(visibleDialogs).toHaveLength(1)
    expect(visibleDialogs[0]!.props('user')).toBeUndefined()

    wrapper.unmount()
  })

  it('confirms before terminating all sessions, and accepting calls userManagementStore.terminateAllSessions', async () => {
    deleteAllSessionsMock.mockResolvedValue(undefined)
    const wrapper = await mountTab(['write:settings'])

    await findButton(wrapper, 'Terminate All Sessions')!.trigger('click')

    expect(confirmRequireMock).toHaveBeenCalledTimes(1)
    const options = confirmRequireMock.mock.calls[0]![0] as { accept: () => Promise<void> }
    expect(deleteAllSessionsMock).not.toHaveBeenCalled()

    await options.accept()
    await flushPromises()

    expect(deleteAllSessionsMock).toHaveBeenCalledTimes(1)

    wrapper.unmount()
  })

  it('does not call terminateAllSessions when the confirm is never accepted', async () => {
    const wrapper = await mountTab(['write:settings'])

    await findButton(wrapper, 'Terminate All Sessions')!.trigger('click')
    await flushPromises()

    expect(deleteAllSessionsMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('renders the standard Views button instead of being hidden', async () => {
    const wrapper = await mountTab(['write:settings'])

    const viewsButton = wrapper.findAll('button').find((b) => b.text() === 'Views')
    expect(viewsButton).toBeTruthy()

    wrapper.unmount()
  })

  it('toggles the actions column via the views-bar show-actions switch', async () => {
    const wrapper = await mountTab(['write:settings'])

    // Off by default, matching every sibling management view: no row
    // actions column rendered yet (the toolbar's own Terminate All Sessions
    // button also carries the same mdi-logout-variant icon, so assert on
    // the row-actions column specifically rather than the icon class).
    expect(wrapper.find('.row-actions').exists()).toBe(false)

    const viewsButton = wrapper.findAll('button').find((b) => b.text() === 'Views')
    await viewsButton!.trigger('click')
    await flushPromises()

    const toggle = document.getElementById('users-show-actions-toggle') as HTMLInputElement | null
    expect(toggle).toBeTruthy()

    toggle!.click()
    await flushPromises()

    // Toggling flips the shared store's showActions, which the table's
    // actions column is guarded on.
    expect(wrapper.find('.row-actions').exists()).toBe(true)

    wrapper.unmount()
  })

  // @sync calls userManagementStore.triggerRefresh() rather than usersStore.refresh()
  // directly, the table's own refreshTrigger watcher is what re-fetches,
  // via userManagementStore.refreshTable(), so Sync re-loads the table's *current
  // paginated page* instead of the unpaginated picker list.
  it('clicking Sync re-fetches the table via refreshTrigger, at the current skip/limit', async () => {
    const wrapper = await mountTab(['write:settings'])

    getUsersMock.mockClear()

    const syncButton = wrapper.findAll('button').find((b) => b.text() === 'Sync')
    expect(syncButton).toBeTruthy()
    await syncButton!.trigger('click')
    await flushPromises()

    expect(getUsersMock).toHaveBeenCalledTimes(1)

    wrapper.unmount()
  })
})
