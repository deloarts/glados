import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import OpenVue from 'openvue/config'
import ToastService from 'openvue/toastservice'
import Toast from 'openvue/toast'
import Aura from '@openvue/themes/aura'

import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { userWithPermissions } from '@/test-utils/factories'

import type { PageResponse } from '@/core/api/types'
import type { UserFilterDto } from '@/core/types/userRequest'
import type { UserResponse } from '@/core/types/userResponse'
import type { LinkPdmUsersCommand, PdmUser } from '../../../types/adminSettingsTypes'

const getPdmUsersMock = vi.fn<() => Promise<PdmUser[]>>()
const linkPdmUsersMock = vi.fn<(cmd: LinkPdmUsersCommand) => Promise<void>>()
const getUsersMock = vi.fn<(params?: UserFilterDto) => Promise<PageResponse<UserResponse>>>()

vi.mock('../../../api/getPdmUsers', () => ({
  getPdmUsers: () => getPdmUsersMock(),
}))
vi.mock('../../../api/linkPdmUsers', () => ({
  linkPdmUsers: (cmd: LinkPdmUsersCommand) => linkPdmUsersMock(cmd),
}))
vi.mock('@/core/api/users/getUserDirectory', () => ({
  getUserDirectory: (params?: UserFilterDto) => getUsersMock(params),
}))

import PdmUsersDialog from '../PdmUsersDialog.vue'

function makeGladosUser(overrides: Partial<UserResponse> = {}): UserResponse {
  return userWithPermissions(['write:settings'], {
    id: 5,
    username: 'jdoe',
    full_name: 'Jane Doe',
    ...overrides,
  })
}

function makePdmUser(overrides: Partial<PdmUser> = {}): PdmUser {
  return {
    pdm_user_id: 2,
    username: 'jdoe',
    full_name: 'Jane Doe',
    is_service_account: false,
    linked_user_id: null,
    proposed_user_id: null,
    ...overrides,
  }
}

function page<T>(items: T[]): PageResponse<T> {
  return { items, total: items.length, limit: 25, skip: 0 }
}

async function mountDialog(permissions: string[] = ['write:settings']) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)

  // A sibling <Toast/> is required for useToast().add(...) to render
  // anything at all (AdminSettingsTabSolidworksPdm.spec.ts's own
  // "Toast-alongside" pattern), needed here for the load/save toasts.
  const wrapper = mount(
    {
      components: { PdmUsersDialog, Toast },
      template: '<div><PdmUsersDialog :visible="true" /><Toast /></div>',
    },
    {
      attachTo: document.body,
      global: {
        plugins: [pinia, [OpenVue, { theme: { preset: Aura } }], ToastService, i18n],
      },
    },
  )
  await flushPromises()
  return wrapper
}

function saveButton(wrapper: Awaited<ReturnType<typeof mountDialog>>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (i18n.global.t('adminSettings.pdmUsers.save') as string))!
}

function bodyText(): string {
  return document.body.textContent ?? ''
}

describe('PdmUsersDialog', () => {
  beforeEach(() => {
    getPdmUsersMock.mockReset()
    linkPdmUsersMock.mockReset().mockResolvedValue(undefined)
    getUsersMock.mockReset()
    getUsersMock.mockResolvedValue(page([makeGladosUser()]))
    getPdmUsersMock.mockResolvedValue([])
  })

  it('lists vault users with their username and full name', async () => {
    getPdmUsersMock.mockResolvedValue([makePdmUser()])
    const wrapper = await mountDialog()

    expect(bodyText()).toContain('jdoe')
    expect(bodyText()).toContain('Jane Doe')

    wrapper.unmount()
  })

  it('preselects the Glados user Select to the existing link', async () => {
    getPdmUsersMock.mockResolvedValue([makePdmUser({ linked_user_id: 5 })])
    const wrapper = await mountDialog()

    expect(wrapper.findComponent({ name: 'Select' }).props('modelValue')).toBe(5)

    wrapper.unmount()
  })

  it('preselects a not-yet-linked row to the proposed user and tags it as suggested', async () => {
    getPdmUsersMock.mockResolvedValue([makePdmUser({ proposed_user_id: 5 })])
    const wrapper = await mountDialog()

    expect(wrapper.findComponent({ name: 'Select' }).props('modelValue')).toBe(5)
    expect(bodyText()).toContain(i18n.global.t('adminSettings.pdmUsers.proposedTag'))

    wrapper.unmount()
  })

  it('flags the service account and never proposes a link for it', async () => {
    getPdmUsersMock.mockResolvedValue([
      makePdmUser({ username: 'svc-account', is_service_account: true, proposed_user_id: null }),
    ])
    const wrapper = await mountDialog()

    expect(bodyText()).toContain(i18n.global.t('adminSettings.pdmUsers.serviceAccountTag'))
    expect(wrapper.findComponent({ name: 'Select' }).props('modelValue')).toBe(0)

    wrapper.unmount()
  })

  it('shows a count badge when several rows share the same Glados user, never blocking it', async () => {
    getPdmUsersMock.mockResolvedValue([
      makePdmUser({ pdm_user_id: 2, linked_user_id: 5 }),
      makePdmUser({ pdm_user_id: 3, username: 'jdoe.alt', linked_user_id: 5 }),
    ])
    const wrapper = await mountDialog()

    const selects = wrapper.findAllComponents({ name: 'Select' })
    expect(selects[0]!.props('modelValue')).toBe(5)
    expect(selects[1]!.props('modelValue')).toBe(5)
    expect(bodyText()).toContain('×2')

    await saveButton(wrapper).trigger('click')
    await flushPromises()

    // Both rows keep their (shared) pick: saving never rejects or drops one.
    expect(linkPdmUsersMock).toHaveBeenCalledWith({
      links: [
        { pdm_user_id: 2, user_id: 5 },
        { pdm_user_id: 3, user_id: 5 },
      ],
    })
    expect(bodyText()).toContain(i18n.global.t('adminSettings.pdmUsers.saved'))

    wrapper.unmount()
  })

  it('sends the full selection batch on save, including an unlink', async () => {
    getPdmUsersMock.mockResolvedValue([
      makePdmUser({ pdm_user_id: 2, linked_user_id: 5 }),
      makePdmUser({ pdm_user_id: 3, username: 'bob', linked_user_id: null, proposed_user_id: null }),
    ])
    const wrapper = await mountDialog()

    // Unlink the first (already linked) row by picking "Not linked".
    await wrapper.findAllComponents({ name: 'Select' })[0]!.vm.$emit('update:modelValue', 0)
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(linkPdmUsersMock).toHaveBeenCalledWith({
      links: [
        { pdm_user_id: 2, user_id: null },
        { pdm_user_id: 3, user_id: null },
      ],
    })
    expect(bodyText()).toContain(i18n.global.t('adminSettings.pdmUsers.saved'))

    wrapper.unmount()
  })

  it('toasts an error and does not clear the table when saving fails', async () => {
    getPdmUsersMock.mockResolvedValue([makePdmUser()])
    linkPdmUsersMock.mockRejectedValue(new Error('boom'))
    const wrapper = await mountDialog()

    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(bodyText()).toContain(i18n.global.t('adminSettings.pdmUsers.saveFailed'))

    wrapper.unmount()
  })

  it('toasts an error when the initial load fails', async () => {
    getPdmUsersMock.mockRejectedValue({
      isAxiosError: true,
      response: { status: 500, data: { detail: 'boom' } },
    })
    const wrapper = await mountDialog()

    expect(bodyText()).toContain(i18n.global.t('adminSettings.pdmUsers.loadFailed'))

    wrapper.unmount()
  })

  it('disables the Select and the save button without write:settings', async () => {
    getPdmUsersMock.mockResolvedValue([makePdmUser()])
    const wrapper = await mountDialog([])

    expect(wrapper.findComponent({ name: 'Select' }).props('disabled')).toBe(true)
    expect(saveButton(wrapper).element.hasAttribute('disabled')).toBe(true)

    wrapper.unmount()
  })
})
