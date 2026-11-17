import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeUserResponse } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { Permission } from '@/core/auth/permissions'
import { i18n } from '@/core/i18n'
import { patsApi } from '../../api/patsApi'
import { usePatsStore } from '../../stores/patsStore'

import type { UserResponse } from '@/core/types/userResponse'

import AccountAccessTokenView from '../AccountAccessTokenView.vue'

const t = i18n.global.t

// TokenManagementControls is stubbed below, but Vue Test Utils still renders
// a stubbed component's slots by default, including the #handbook slot's
// HelpButton, whose defensive useRoute() call needs a router to be
// installed at all. Mirrors BoughtItemsCatalogueControls.spec.ts.
const router = createRouter({ history: createMemoryHistory(), routes: [] })

function mountView(userOverrides: Partial<UserResponse> = {}, pdmEnabled = false) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = makeUserResponse(userOverrides)
  useHostStore().pdmEnabled = pdmEnabled

  return mountWithApp(AccountAccessTokenView, {
    pinia,
    global: {
      plugins: [router],
      stubs: {
        TokenManagementControls: true,
        TokenManagementViews: true,
        TokenManagementTable: true,
      },
    },
  })
}

describe('AccountAccessTokenView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('passes the pats store, api, and i18n prefix through to the views bar and table', () => {
    const wrapper = mountView({ permissions: [Permission.WRITE_PAT] })

    const views = wrapper.findComponent({ name: 'TokenManagementViews' })
    expect(views.props('store')).toBe(usePatsStore())

    const table = wrapper.findComponent({ name: 'TokenManagementTable' })
    expect(table.props('store')).toBe(usePatsStore())
    expect(table.props('api')).toBe(patsApi)
    expect(table.props('canManage')).toBe(true)
    expect(table.props('i18nPrefix')).toBe('account.pat')

    wrapper.unmount()
  })

  it('gates canCreate on write:pat but lets an owner revoke their own tokens without it', () => {
    const withoutPermission = mountView({ permissions: [] })
    const controlsWithout = withoutPermission.findComponent({ name: 'TokenManagementControls' })
    expect(controlsWithout.props('canManage')).toBe(true)
    expect(controlsWithout.props('canCreate')).toBe(false)
    expect(controlsWithout.props('createBlocked')).toBe(
      'This needs the permission Write Access Token.',
    )
    expect(
      withoutPermission.findComponent({ name: 'TokenManagementTable' }).props('canManage'),
    ).toBe(true)
    withoutPermission.unmount()

    const withPermission = mountView({ permissions: [Permission.WRITE_PAT] })
    const controlsWith = withPermission.findComponent({ name: 'TokenManagementControls' })
    expect(controlsWith.props('canManage')).toBe(true)
    expect(controlsWith.props('canCreate')).toBe(true)
    expect(controlsWith.props('createBlocked')).toBe('')
    withPermission.unmount()
  })

  it('shows the add-in shortcut disabled rather than hidden without write:pat', () => {
    const wrapper = mountView({ permissions: [] }, true)
    const controls = wrapper.findComponent({ name: 'TokenManagementControls' })
    expect(controls.props('showCreateAddin')).toBe(true)
    expect(controls.props('canCreate')).toBe(false)
    wrapper.unmount()
  })

  it('only offers the SolidWorks add-in shortcut once PDM is enabled', () => {
    const pdmOff = mountView({ permissions: [Permission.WRITE_PAT] }, false)
    expect(
      pdmOff.findComponent({ name: 'TokenManagementControls' }).props('showCreateAddin'),
    ).toBe(false)
    pdmOff.unmount()

    const pdmOn = mountView({ permissions: [Permission.WRITE_PAT] }, true)
    expect(
      pdmOn.findComponent({ name: 'TokenManagementControls' }).props('showCreateAddin'),
    ).toBe(true)
    pdmOn.unmount()
  })

  it('offers the PDM add-in shortcut once PDM is enabled, never to a system user', () => {
    const showsPdm = (wrapper: ReturnType<typeof mountView>) =>
      wrapper.findComponent({ name: 'TokenManagementControls' }).props('showCreatePdmAddin')

    const pdmOff = mountView({ permissions: [Permission.WRITE_PAT] }, false)
    expect(showsPdm(pdmOff)).toBe(false)
    pdmOff.unmount()

    const pdmOn = mountView({ permissions: [Permission.WRITE_PAT] }, true)
    expect(showsPdm(pdmOn)).toBe(true)
    pdmOn.unmount()

    const system = mountView({ is_systemuser: true, permissions: [Permission.WRITE_PAT] }, true)
    expect(showsPdm(system)).toBe(false)
    system.unmount()
  })

  it('locks a system user out of creating tokens (but not managing them) and shows the system-user message', () => {
    const wrapper = mountView({ is_systemuser: true, permissions: [Permission.WRITE_PAT] }, true)

    const controls = wrapper.findComponent({ name: 'TokenManagementControls' })
    expect(controls.props('canManage')).toBe(true)
    expect(controls.props('canCreate')).toBe(false)
    expect(controls.props('showCreateAddin')).toBe(false)
    expect(controls.props('createBlocked')).toBe('')
    expect(wrapper.text()).toContain(t('account.pat.systemUserNoCreate'))

    wrapper.unmount()
  })
})
