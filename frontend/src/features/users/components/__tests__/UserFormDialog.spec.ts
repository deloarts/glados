import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { ConfirmationOptions } from 'openvue/confirmationoptions'
import type { ToastMessageOptions } from 'openvue/toast'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeUserResponse } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { i18n } from '@/core/i18n'
import type { UserResponse } from '@/core/types/userResponse'
import type { UserCreateRequest, UserUpdateRequest } from '@/core/types/userRequest'

const getUsersMock =
  vi.fn<() => Promise<{ items: UserResponse[]; total: number; limit: number; skip: number }>>()
const createUserMock = vi.fn<(payload: UserCreateRequest) => Promise<UserResponse>>()
const updateUserMock = vi.fn<(id: number, payload: UserUpdateRequest) => Promise<UserResponse>>()
const resetUserTotpMock = vi.fn<(id: number) => Promise<void>>()
const uploadUserAvatarMock = vi.fn<(id: number, file: File) => Promise<UserResponse>>()
const deleteUserAvatarMock = vi.fn<(id: number) => Promise<UserResponse>>()

vi.mock('@/core/api/users/getUserDirectory', () => ({
  getUserDirectory: () => getUsersMock(),
}))
vi.mock('../../api/createUser', () => ({
  createUser: (payload: UserCreateRequest) => createUserMock(payload),
}))
vi.mock('@/core/api/users/updateUser', () => ({
  updateUser: (id: number, payload: UserUpdateRequest) => updateUserMock(id, payload),
}))
vi.mock('../../api/resetUserTotp', () => ({
  resetUserTotp: (id: number) => resetUserTotpMock(id),
}))
vi.mock('../../api/uploadUserAvatar', () => ({
  uploadUserAvatar: (id: number, file: File) => uploadUserAvatarMock(id, file),
}))
vi.mock('../../api/deleteUserAvatar', () => ({
  deleteUserAvatar: (id: number) => deleteUserAvatarMock(id),
}))
// Opening an existing user loads its avatar. Left unmocked, that request
// reaches whatever answers on the API port, and a 401 from a running dev
// backend signs the seeded current user out halfway through a test.
vi.mock('@/core/api/users/getUserAvatar', () => ({
  getUserAvatar: () => Promise.resolve(null),
}))

// Same technique as OrdersTable.spec.ts: replace the composable entirely so
// the `accept`/`reject` callbacks can be invoked directly, without mounting
// a real <ConfirmDialog/> and driving its DOM.
const confirmRequireMock = vi.fn<(options: ConfirmationOptions) => void>()
vi.mock('openvue/useconfirm', () => ({
  useConfirm: () => ({ require: confirmRequireMock }),
}))

// Same technique, for toast.add(): lets the new avatar-failure tests assert
// what was shown without driving the real ToastService's DOM/timing.
const toastAddMock = vi.fn<(options: ToastMessageOptions) => void>()
vi.mock('openvue/usetoast', () => ({
  useToast: () => ({ add: toastAddMock }),
}))

// Opening an existing user loads its passkey count, which would reach the
// API URL the same way.
vi.mock('../../api/userPasskeys', () => ({
  fetchUserPasskeys: () => Promise.resolve([]),
  resetUserPasskeys: () => Promise.resolve(0),
}))
// The users table and dialog load the groups. Unmocked, that request reaches
// whatever answers on the API URL, like the other requests mocked here.
vi.mock('@/features/users/api/userGroups', () => ({
  getUserGroups: () => Promise.resolve([]),
  createUserGroup: () => Promise.reject(new Error('not used')),
  updateUserGroup: () => Promise.reject(new Error('not used')),
  deleteUserGroup: () => Promise.resolve(),
}))

import UserFormDialog from '../UserFormDialog.vue'

type FormVm = {
  form: {
    username: string
    full_name: string
    email: string
    password: string
    is_shared_account: boolean
    member_ids: number[]
    permissions: string[]
    auth_provider: string
  }
  isLdap: boolean
  passwordRequired: boolean
  errorMessage: string | null
  canResetTotp: boolean
  needsCurrentPassword: boolean
  currentPassword: string
}

// Mounts closed and opens via setProps, mirroring the reset-on-open watcher
// convention used across the other dialogs (ProductionOrderCompletionDialog,
// OrderCreateForm): the watcher only fires on a false -> true transition.
async function mountDialog(
  props: { user?: UserResponse } = {},
  currentUserPermissions: string[] = ['write:settings'],
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = makeUserResponse({ id: 999, permissions: currentUserPermissions })

  const wrapper = mountWithApp(UserFormDialog, {
    pinia,
    attachTo: document.body,
    props: { visible: false, ...props },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

// The Dialog teleports its content to document.body, so plain native-element
// lookups (`wrapper.find`) never see it; only component-tree lookups
// (`findComponent`/`findAllComponents`) resolve through the teleport,
// because they follow the element the component actually rendered to,
// wherever the DOM moved it. Native elements (inputs, labels, the <form>
// itself) are queried straight off `document` instead, the same convention
// OrderCreateForm.spec.ts and SourceItemCreateForm.spec.ts use.
function findButton(wrapper: VueWrapper, label: string) {
  return wrapper.findAllComponents({ name: 'Button' }).find((b) => b.props('label') === label)
}

async function clickSave(wrapper: VueWrapper) {
  await findButton(wrapper, 'Save')!.trigger('click')
  await flushPromises()
}

describe('UserFormDialog', () => {
  beforeEach(() => {
    getUsersMock.mockReset()
    createUserMock.mockReset()
    updateUserMock.mockReset()
    resetUserTotpMock.mockReset()
    uploadUserAvatarMock.mockReset()
    deleteUserAvatarMock.mockReset()
    confirmRequireMock.mockReset()
    toastAddMock.mockReset()
    getUsersMock.mockResolvedValue({ items: [], total: 0, limit: 100, skip: 0 })
  })

  it('renders the "Create User" header and an empty form when no user prop is given', async () => {
    const wrapper = await mountDialog()

    expect(wrapper.findComponent({ name: 'Dialog' }).props('header')).toBe('Create User')
    expect((document.querySelector('#u-username') as HTMLInputElement).value).toBe('')

    wrapper.unmount()
  })

  it('renders the "Edit User" header and populates the form from the user prop', async () => {
    const user = makeUserResponse({ username: 'asmith', full_name: 'Alice Smith' })
    const wrapper = await mountDialog({ user })

    expect(wrapper.findComponent({ name: 'Dialog' }).props('header')).toBe('Edit User')
    expect((document.querySelector('#u-username') as HTMLInputElement).value).toBe('asmith')
    expect((document.querySelector('#u-full-name') as HTMLInputElement).value).toBe('Alice Smith')

    wrapper.unmount()
  })

  // The whole app renders times in the tenant's default timezone, so a user
  // has no zone of their own to pick or send.
  it('offers no timezone field and sends no timezone in the update payload', async () => {
    const user = makeUserResponse({ id: 5 })
    updateUserMock.mockResolvedValue(user)
    const wrapper = await mountDialog({ user })

    expect(document.querySelector('#u-timezone')).toBeNull()
    expect(document.querySelector('#u-date-format')).not.toBeNull()

    await clickSave(wrapper)

    expect(updateUserMock).toHaveBeenCalledOnce()
    expect(Object.keys(updateUserMock.mock.calls[0]![1])).not.toContain('timezone')

    wrapper.unmount()
  })

  it('shows every linked PDM user, and a "none" hint when there are none', async () => {
    const linked = makeUserResponse({
      pdm_links: [
        { pdm_user_id: 2, pdm_username: 'jdoe', linked_at: '2026-01-01T00:00:00Z' },
        { pdm_user_id: 3, pdm_username: 'jdoe.alt', linked_at: '2026-01-02T00:00:00Z' },
      ],
    })
    const linkedWrapper = await mountDialog({ user: linked })
    const pdmLinksField = document.querySelector('#u-pdm-links') as HTMLElement
    expect(pdmLinksField.textContent).toContain('jdoe (#2)')
    expect(pdmLinksField.textContent).toContain('jdoe.alt (#3)')
    linkedWrapper.unmount()

    const unlinked = makeUserResponse({ pdm_links: [] })
    const unlinkedWrapper = await mountDialog({ user: unlinked })
    expect(
      (document.querySelector('#u-pdm-links') as HTMLElement).textContent,
    ).toContain('No PDM users linked')
    unlinkedWrapper.unmount()

    const createWrapper = await mountDialog()
    expect(document.querySelector('#u-pdm-links')).toBeNull()
    createWrapper.unmount()
  })

  it('blocks submit and shows the required-fields error when username/full_name/email are missing', async () => {
    const wrapper = await mountDialog()

    await clickSave(wrapper)

    const vm = wrapper.vm as unknown as FormVm
    expect(vm.errorMessage).toBe('Please fill in all required fields.')
    expect(createUserMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('requires a password on a new local account but not when editing an existing local one', async () => {
    const createWrapper = await mountDialog()
    expect((createWrapper.vm as unknown as FormVm).passwordRequired).toBe(true)
    createWrapper.unmount()

    const editWrapper = await mountDialog({ user: makeUserResponse({ auth_provider: 'local' }) })
    expect((editWrapper.vm as unknown as FormVm).passwordRequired).toBe(false)
    editWrapper.unmount()
  })

  it('requires a password again when moving an LDAP account back to local', async () => {
    const wrapper = await mountDialog({ user: makeUserResponse({ auth_provider: 'ldap' }) })
    const vm = wrapper.vm as unknown as FormVm

    expect(vm.isLdap).toBe(true)
    vm.form.auth_provider = 'local'
    await flushPromises()

    expect(vm.passwordRequired).toBe(true)

    wrapper.unmount()
  })

  it('hides the password field and shows the LDAP hint when auth_provider is ldap', async () => {
    const wrapper = await mountDialog()
    const vm = wrapper.vm as unknown as FormVm

    expect(document.querySelector('#u-password')).not.toBeNull()

    vm.form.auth_provider = 'ldap'
    await flushPromises()

    expect(document.querySelector('#u-password')).toBeNull()
    expect(document.querySelector('.hint')?.textContent).toBe(
      "Not needed. The directory holds this account's password.",
    )

    wrapper.unmount()
  })

  it('requires at least one shared-account member before submit', async () => {
    const wrapper = await mountDialog()
    const vm = wrapper.vm as unknown as FormVm

    vm.form.username = 'shared'
    vm.form.full_name = 'Shared Account'
    vm.form.email = 'shared@example.com'
    vm.form.password = 'pw'
    vm.form.is_shared_account = true
    await flushPromises()

    await clickSave(wrapper)

    expect(vm.errorMessage).toBe('A shared account needs at least one assigned member.')
    expect(createUserMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it("renders a permission checkbox checked for the user's existing permissions and unchecked otherwise", async () => {
    const wrapper = await mountDialog({
      user: makeUserResponse({
        permissions: ['write:orders'],
        direct_permissions: ['write:orders'],
      }),
    })

    const granted = document.querySelector('input[id="perm-write:orders"]') as HTMLInputElement
    const notGranted = document.querySelector(
      'input[id="perm-write:printers"]',
    ) as HTMLInputElement
    expect(granted.checked).toBe(true)
    expect(notGranted.checked).toBe(false)

    wrapper.unmount()
  })

  it('toggling a permission checkbox adds and removes it from form.permissions', async () => {
    const wrapper = await mountDialog()
    const vm = wrapper.vm as unknown as FormVm
    expect(vm.form.permissions).not.toContain('write:orders')

    const checkbox = document.querySelector('input[id="perm-write:orders"]') as HTMLInputElement
    checkbox.checked = true
    checkbox.dispatchEvent(new Event('change'))
    await flushPromises()
    expect(vm.form.permissions).toContain('write:orders')

    checkbox.checked = false
    checkbox.dispatchEvent(new Event('change'))
    await flushPromises()
    expect(vm.form.permissions).not.toContain('write:orders')

    wrapper.unmount()
  })

  // There is no write:users permission: user management is gated by
  // write:settings, so the dialog must never offer one.
  it('never offers write:users as a grantable permission', async () => {
    const wrapper = await mountDialog()

    expect(document.querySelector('input[id="perm-write:users"]')).toBeNull()

    wrapper.unmount()
  })

  it('renders a real label (not a raw i18n key) for every permission checkbox', async () => {
    const wrapper = await mountDialog()

    const labels = Array.from(document.querySelectorAll('.permission-item label'))
    expect(labels.length).toBeGreaterThan(0)
    for (const label of labels) {
      expect(label.textContent?.trim()).not.toMatch(/^[a-z]+(\.\w+)+$/)
    }

    wrapper.unmount()
  })

  it('renders "Print Documents" for print:documents, previously a raw i18n key with no locale entry', async () => {
    const wrapper = await mountDialog()

    const label = document.querySelector('label[for="perm-print:documents"]')
    expect(label?.textContent?.trim()).toBe('Print Documents')

    wrapper.unmount()
  })

  it('builds the create payload with the exact shape userManagementStore.create expects', async () => {
    createUserMock.mockResolvedValue(makeUserResponse())
    const wrapper = await mountDialog()
    const vm = wrapper.vm as unknown as FormVm

    vm.form.username = '  newuser  '
    vm.form.full_name = '  New User  '
    vm.form.email = '  new@example.com  '
    vm.form.password = '  s3cret  '
    vm.form.permissions = ['write:orders']
    await flushPromises()

    await clickSave(wrapper)

    expect(createUserMock).toHaveBeenCalledWith({
      username: 'newuser',
      full_name: 'New User',
      email: 'new@example.com',
      password: 's3cret',
      is_active: true,
      is_shared_account: false,
      auth_provider: 'local',
      member_ids: [],
      group_ids: [],
      permissions: ['write:orders'],
      language: 'enGB',
      date_format: null,
      theme_preset: null,
      theme_primary: null,
      theme_surface: null,
      theme_dark_mode: false,
    })
    expect(wrapper.emitted('saved')).toBeTruthy()

    wrapper.unmount()
  })

  // hostStore.defaultLanguage defaults to 'enGB' until /host/capabilities
  // answers; the assertion above exercises exactly that initial value. This
  // covers the other half: once the admin has configured a different tenant
  // default, a brand-new user should preselect it instead of a hardcoded
  // 'enGB'. Seeded before opening rather than via mountDialog(): the create
  // form's fields are (re)built by createEmptyForm() the moment the dialog's
  // visible prop flips to true, so hostStore.defaultLanguage must already
  // hold its seeded value by then, not set afterwards.
  it('preselects the create payload language from hostStore.defaultLanguage', async () => {
    createUserMock.mockResolvedValue(makeUserResponse({ language: 'deAT' }))
    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = makeUserResponse({ id: 999, permissions: ['write:settings'] })
    useHostStore().defaultLanguage = 'deAT'

    const wrapper = mountWithApp(UserFormDialog, {
      pinia,
      attachTo: document.body,
      props: { visible: false },
    })
    await wrapper.setProps({ visible: true })
    await flushPromises()

    const vm = wrapper.vm as unknown as FormVm
    vm.form.username = 'newuser'
    vm.form.full_name = 'New User'
    vm.form.email = 'new@example.com'
    vm.form.password = 's3cret'
    await flushPromises()

    await clickSave(wrapper)

    expect(createUserMock).toHaveBeenCalledWith(expect.objectContaining({ language: 'deAT' }))

    wrapper.unmount()
  })

  it('builds the update payload with password: null when the field is left blank (means "unchanged")', async () => {
    const user = makeUserResponse({ id: 5, auth_provider: 'local', permissions: ['write:orders'] })
    updateUserMock.mockResolvedValue(user)
    const wrapper = await mountDialog({ user })
    const vm = wrapper.vm as unknown as FormVm

    vm.form.full_name = 'Renamed'
    await flushPromises()

    await clickSave(wrapper)

    expect(updateUserMock).toHaveBeenCalledWith(
      5,
      expect.objectContaining({ full_name: 'Renamed', password: null }),
    )

    wrapper.unmount()
  })

  it('builds the update payload with the trimmed password when one is provided', async () => {
    const user = makeUserResponse({ id: 5, auth_provider: 'local' })
    updateUserMock.mockResolvedValue(user)
    const wrapper = await mountDialog({ user })
    const vm = wrapper.vm as unknown as FormVm

    vm.form.password = '  newpass123  '
    await flushPromises()

    await clickSave(wrapper)

    expect(updateUserMock).toHaveBeenCalledWith(
      5,
      expect.objectContaining({ password: 'newpass123' }),
    )

    wrapper.unmount()
  })

  it('sends no current password when an administrator sets someone else’s password', async () => {
    const user = makeUserResponse({ id: 5, auth_provider: 'local' })
    updateUserMock.mockResolvedValue(user)
    const wrapper = await mountDialog({ user })
    const vm = wrapper.vm as unknown as FormVm

    vm.form.password = 'newpass123'
    await flushPromises()

    expect(vm.needsCurrentPassword).toBe(false)
    await clickSave(wrapper)

    expect(updateUserMock).toHaveBeenCalledWith(
      5,
      expect.objectContaining({ password: 'newpass123', current_password: null }),
    )

    wrapper.unmount()
  })

  it('asks for the current password before changing your own', async () => {
    const self = makeUserResponse({ id: 999, auth_provider: 'local' })
    updateUserMock.mockResolvedValue(self)
    const wrapper = await mountDialog({ user: self })
    const vm = wrapper.vm as unknown as FormVm

    vm.form.password = 'newpass123'
    await flushPromises()
    expect(vm.needsCurrentPassword).toBe(true)

    await clickSave(wrapper)
    expect(updateUserMock).not.toHaveBeenCalled()
    expect(vm.errorMessage).toBe(i18n.global.t('settings.users.errors.currentPasswordRequired'))

    vm.currentPassword = 'the-old-password'
    await flushPromises()
    await clickSave(wrapper)

    expect(updateUserMock).toHaveBeenCalledWith(
      999,
      expect.objectContaining({ password: 'newpass123', current_password: 'the-old-password' }),
    )

    wrapper.unmount()
  })

  it('sends password: null for an LDAP account update even if a stale value sits in the field', async () => {
    const user = makeUserResponse({ id: 5, auth_provider: 'ldap' })
    updateUserMock.mockResolvedValue(user)
    const wrapper = await mountDialog({ user })
    const vm = wrapper.vm as unknown as FormVm

    // The field is hidden for LDAP accounts, but nothing stops the ref from
    // already holding a stale value (e.g. typed before switching providers).
    vm.form.password = 'stale-value'
    await flushPromises()

    await clickSave(wrapper)

    expect(updateUserMock).toHaveBeenCalledWith(5, expect.objectContaining({ password: null }))

    wrapper.unmount()
  })

  it('renders the reset-2FA action when the acting user has write:settings and the target is eligible', async () => {
    const user = makeUserResponse({ id: 5, totp_enabled: true })
    const wrapper = await mountDialog({ user }, ['write:settings'])

    expect(findButton(wrapper, 'Reset 2FA')).toBeTruthy()

    wrapper.unmount()
  })

  it('shows the reset-2FA action disabled with the missing permission when the acting user lacks write:settings', async () => {
    const user = makeUserResponse({ id: 5, totp_enabled: true })
    const wrapper = await mountDialog({ user }, [])

    const reset = findButton(wrapper, 'Reset 2FA')
    expect(reset?.attributes('disabled')).toBeDefined()
    const span = reset?.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
    expect(span?.$_ptooltipValue).toBe('This needs the permission Write Settings.')

    wrapper.unmount()
  })

  it('hides the reset-2FA action for the system user and for the current user’s own record', async () => {
    const systemUser = makeUserResponse({ id: 5, totp_enabled: true, is_systemuser: true })
    const systemWrapper = await mountDialog({ user: systemUser }, ['write:settings'])
    expect(findButton(systemWrapper, 'Reset 2FA')).toBeUndefined()
    systemWrapper.unmount()

    // mountDialog seeds the current user with id 999.
    const selfUser = makeUserResponse({ id: 999, totp_enabled: true })
    const selfWrapper = await mountDialog({ user: selfUser }, ['write:settings'])
    expect(findButton(selfWrapper, 'Reset 2FA')).toBeUndefined()
    selfWrapper.unmount()
  })

  it('confirms before resetting 2FA, and accepting calls userManagementStore.resetTotp', async () => {
    resetUserTotpMock.mockResolvedValue(undefined)
    const user = makeUserResponse({ id: 5, username: 'target-user', totp_enabled: true })
    const wrapper = await mountDialog({ user }, ['write:settings'])

    await findButton(wrapper, 'Reset 2FA')!.trigger('click')

    expect(confirmRequireMock).toHaveBeenCalledTimes(1)
    const options = confirmRequireMock.mock.calls[0]![0] as {
      accept: () => Promise<void>
    }
    expect(resetUserTotpMock).not.toHaveBeenCalled()

    await options.accept()
    await flushPromises()

    expect(resetUserTotpMock).toHaveBeenCalledWith(5)

    wrapper.unmount()
  })

  // Like onSubmit and onResetTotp, onAvatarSelected/onDeleteAvatar catch
  // a rejected store call and surface it via toast.add (same mechanism as
  // onResetTotp), instead of re-throwing with no user-facing feedback.
  it('surfaces an avatar-upload failure via a toast instead of failing silently', async () => {
    const user = makeUserResponse({ id: 5, username: 'target-user', has_avatar: false })
    const wrapper = await mountDialog({ user })
    const vm = wrapper.vm as unknown as {
      onAvatarSelected: (e: Event) => Promise<void>
      uploadingAvatar: boolean
    }

    const error = new Error('storage backend unreachable')
    uploadUserAvatarMock.mockRejectedValue(error)

    const file = new File(['x'], 'avatar.png', { type: 'image/png' })
    const input = document.createElement('input')
    Object.defineProperty(input, 'files', { value: [file] })
    const event = { target: input } as unknown as Event

    await expect(vm.onAvatarSelected(event)).resolves.toBeUndefined()
    expect(vm.uploadingAvatar).toBe(false)
    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({
        severity: 'error',
        summary: 'target-user',
        detail: 'Avatar upload failed. Please try again.',
      }),
    )

    wrapper.unmount()
  })

  it('surfaces an avatar-delete failure via a toast instead of failing silently', async () => {
    // has_avatar: false, matching the sibling upload-failure test above;
    // onDeleteAvatar is invoked directly here and doesn't depend on an
    // existing avatar, and true would trigger the real (unmocked)
    // avatarsStore.fetch() in the dialog's open-watcher.
    const user = makeUserResponse({ id: 5, username: 'target-user', has_avatar: false })
    const wrapper = await mountDialog({ user })
    const vm = wrapper.vm as unknown as {
      onDeleteAvatar: () => Promise<void>
      deletingAvatar: boolean
    }

    const error = new Error('storage backend unreachable')
    deleteUserAvatarMock.mockRejectedValue(error)

    await expect(vm.onDeleteAvatar()).resolves.toBeUndefined()
    expect(vm.deletingAvatar).toBe(false)
    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({
        severity: 'error',
        summary: 'target-user',
        detail: 'Avatar removal failed. Please try again.',
      }),
    )

    wrapper.unmount()
  })

  it('closes the dialog without saving when Cancel is clicked', async () => {
    const wrapper = await mountDialog()

    await findButton(wrapper, 'Cancel')!.trigger('click')
    await flushPromises()

    expect(wrapper.emitted('update:visible')?.at(-1)).toEqual([false])
    expect(createUserMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })
})
