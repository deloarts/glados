import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeUserResponse } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { i18n } from '@/core/i18n'

const putMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    put: (url: string, payload: unknown) => putMock(url, payload),
  },
}))

import AccountMeView from '../AccountMeView.vue'

const t = i18n.global.t

function saveButton(wrapper: ReturnType<typeof mountWithApp>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (t('common.save') as string))!
}

describe('AccountMeView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    putMock.mockReset()
    putMock.mockResolvedValue({ data: makeUserResponse() })
  })

  // This tab renders inside the shared page shell (PageLayout), same as its
  // sibling account tabs (sessions, PAT, notifications).
  it('renders inside PageLayout and shows the profile settings form', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = makeUserResponse()

    const wrapper = mountWithApp(AccountMeView, { pinia })
    await flushPromises()

    const layout = wrapper.findComponent({ name: 'PageLayout' })
    expect(layout.exists()).toBe(true)

    expect(wrapper.text()).toContain(t('accountMe.profile.fullName'))
    expect(wrapper.text()).toContain(t('accountMe.avatar.title'))
    expect(wrapper.text()).toContain(t('accountMe.theme.preset'))
    expect(wrapper.text()).toContain(t('common.save'))

    wrapper.unmount()
  })

  it('still offers the password-change control for a local account', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = makeUserResponse()

    const wrapper = mountWithApp(AccountMeView, { pinia })
    await flushPromises()

    expect(wrapper.text()).toContain(t('accountMe.password.changeButton'))

    wrapper.unmount()
  })

  it('asks for the current password and sends it with the new one', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = makeUserResponse()
    const wrapper = mountWithApp(AccountMeView, { pinia, attachTo: document.body })
    await flushPromises()

    const passwordButtons = () =>
      wrapper
        .findAllComponents({ name: 'Button' })
        .filter((b) => b.props('label') === (t('accountMe.password.change') as string))
    await passwordButtons()[0]!.trigger('click')
    await flushPromises()
    const dialog = wrapper
      .findAllComponents({ name: 'Dialog' })
      .find((d) => d.props('header') === (t('accountMe.password.dialogTitle') as string))!
    const [current, next, confirm] = dialog.findAllComponents({ name: 'InputText' })
    await current!.vm.$emit('update:modelValue', 'the-old-password')
    await next!.vm.$emit('update:modelValue', 'a-new-strong-password')
    await confirm!.vm.$emit('update:modelValue', 'a-new-strong-password')
    await passwordButtons().at(-1)!.trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith('/users/me', {
      password: 'a-new-strong-password',
      current_password: 'the-old-password',
    })

    wrapper.unmount()
  })

  it('does not send a password change without the current password', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = makeUserResponse()
    const wrapper = mountWithApp(AccountMeView, { pinia, attachTo: document.body })
    await flushPromises()

    const passwordButtons = () =>
      wrapper
        .findAllComponents({ name: 'Button' })
        .filter((b) => b.props('label') === (t('accountMe.password.change') as string))
    await passwordButtons()[0]!.trigger('click')
    await flushPromises()
    const dialog = wrapper
      .findAllComponents({ name: 'Dialog' })
      .find((d) => d.props('header') === (t('accountMe.password.dialogTitle') as string))!
    const [, next, confirm] = dialog.findAllComponents({ name: 'InputText' })
    await next!.vm.$emit('update:modelValue', 'a-new-strong-password')
    await confirm!.vm.$emit('update:modelValue', 'a-new-strong-password')
    await passwordButtons().at(-1)!.trigger('click')
    await flushPromises()

    expect(putMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('shows the date preview as its own sentence after the hint', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = makeUserResponse()

    const wrapper = mountWithApp(AccountMeView, { pinia })
    await flushPromises()

    const dateHint = wrapper
      .findAll('.regional-hint')
      .map((h) => h.text())
      .find((text) => text.startsWith(t('accountMe.regional.dateFormatHint') as string))!

    expect(dateHint).not.toMatch(/\.\s*,/)
    expect(dateHint).toContain(t('accountMe.regional.dateFormatExample', { date: '' }).trim())

    wrapper.unmount()
  })

  // Every user sees the tenant's timezone from the general settings, so the
  // account page offers no zone of its own and never sends one.
  it('offers no timezone field and sends no timezone on Save', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = makeUserResponse()
    useHostStore().timezones = ['Europe/Vienna', 'Asia/Tokyo']

    const wrapper = mountWithApp(AccountMeView, { pinia })
    await flushPromises()

    expect(wrapper.text()).not.toContain('Timezone')
    expect(
      wrapper.findAllComponents({ name: 'Select' }).some((s) => {
        const options = s.props('options') as unknown[] | undefined
        return options?.includes('Asia/Tokyo') ?? false
      }),
    ).toBe(false)

    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledOnce()
    expect(Object.keys(putMock.mock.calls[0]![1] as object)).not.toContain('timezone')

    wrapper.unmount()
  })

  describe('start page', () => {
    beforeEach(() => {
      setActivePinia(createPinia())
    })

    it("reflects the user's start_page in the Select, labelled via the sidebar keys", async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      useCurrentUserStore().user = makeUserResponse({ start_page: 'production' })
      useHostStore().startPages = ['dashboard', 'todo', 'production']

      const wrapper = mountWithApp(AccountMeView, { pinia })
      await flushPromises()

      const row = wrapper.findAll('.field-row').find((r) => r.text().includes(t('accountMe.regional.startPage') as string))!
      const select = row.findComponent({ name: 'Select' })

      expect(select.props('modelValue')).toBe('production')
      expect(wrapper.text()).toContain(t('main.sidebar.production.label'))

      wrapper.unmount()
    })

    it('includes the selected start_page in the PUT /users/me payload on Save', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      useCurrentUserStore().user = makeUserResponse({ start_page: 'dashboard' })
      useHostStore().startPages = ['dashboard', 'todo', 'production']

      const wrapper = mountWithApp(AccountMeView, { pinia })
      await flushPromises()

      const row = wrapper.findAll('.field-row').find((r) => r.text().includes(t('accountMe.regional.startPage') as string))!
      await row.findComponent({ name: 'Select' }).vm.$emit('update:modelValue', 'production')
      await saveButton(wrapper).trigger('click')
      await flushPromises()

      expect(putMock).toHaveBeenCalledWith(
        '/users/me',
        expect.objectContaining({ start_page: 'production' }),
      )

      wrapper.unmount()
    })
  })
})
