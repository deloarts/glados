import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeUserResponse } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { Permission } from '@/core/auth/permissions'
import { i18n } from '@/core/i18n'

import deAT from '@/core/i18n/locales/de-AT'
import enGB from '@/core/i18n/locales/en-GB'
import AccountPermissionsView from '../AccountPermissionsView.vue'
import { PERMISSION_GROUPS } from '@/shared/utils/permissionGroups'

const t = i18n.global.t

describe('AccountPermissionsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  // This tab renders inside PageLayout with the card disabled, since the
  // group cards already provide their own card chrome, matching its
  // sibling account tabs.
  it('renders inside PageLayout (card disabled) and lists the permission groups', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = makeUserResponse({ permissions: [Permission.WRITE_BOUGHT_ITEMS] })

    const wrapper = mountWithApp(AccountPermissionsView, { pinia })

    const layout = wrapper.findComponent({ name: 'PageLayout' })
    expect(layout.exists()).toBe(true)
    expect(layout.props('card')).toBe(false)

    expect(wrapper.text()).toContain(t('accountMe.permissions.groups.boughtItems'))
    expect(wrapper.find('code').exists()).toBe(false)
    expect(wrapper.find('[data-permission="write:bought_items"] .permission-label').text()).toBe(
      t('settings.users.permissions.writeBoughtItems'),
    )

    wrapper.unmount()
  })

  it('lists every permission a user can be given, with a description in both languages', () => {
    const listed = PERMISSION_GROUPS.flatMap((group) => group.permissions.map((entry) => entry.key))
    expect(Permission.ALL.filter((key) => !listed.includes(key))).toEqual([])

    const missing = (messages: unknown) =>
      PERMISSION_GROUPS.flatMap((group) => [group.titleKey, ...group.permissions.map((entry) => entry.descriptionKey)]).filter(
        (key) => typeof key.split('.').reduce<unknown>((node, part) => (node as Record<string, unknown> | undefined)?.[part], messages) !== 'string',
      )
    expect(missing(enGB)).toEqual([])
    expect(missing(deAT)).toEqual([])
  })

  it('has a label for every listed permission in both languages, always granted read access included', () => {
    const labelKey = (key: string) =>
      `settings.users.permissions.${key.replace(':', '_').replace(/_([a-z])/g, (_, c: string) => c.toUpperCase())}`
    const unlabelled = (messages: unknown) =>
      PERMISSION_GROUPS.flatMap((group) => group.permissions.map((entry) => labelKey(entry.key))).filter(
        (key) => typeof key.split('.').reduce<unknown>((node, part) => (node as Record<string, unknown> | undefined)?.[part], messages) !== 'string',
      )
    expect(unlabelled(enGB)).toEqual([])
    expect(unlabelled(deAT)).toEqual([])
  })

  it('marks a granted checklist permission and leaves the others locked', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = makeUserResponse({ permissions: [Permission.WRITE_CHECKLISTS] })

    const wrapper = mountWithApp(AccountPermissionsView, { pinia })
    const row = (key: string) => wrapper.find(`[data-permission="${key}"]`)

    expect(row('write:checklists')?.classes()).toContain('permission-row--granted')
    expect(row('release:checklists')?.classes()).toContain('permission-row--denied')
    expect(wrapper.text()).toContain(t('accountMe.permissions.groups.calculations'))

    wrapper.unmount()
  })

  it('shows the system-user banner for a system account', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = makeUserResponse({ is_systemuser: true })

    const wrapper = mountWithApp(AccountPermissionsView, { pinia })

    expect(wrapper.text()).toContain(t('accountMe.permissions.systemUser.title'))

    wrapper.unmount()
  })
})
