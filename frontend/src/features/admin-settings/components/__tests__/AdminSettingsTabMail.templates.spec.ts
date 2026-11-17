import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import OpenVue from 'openvue/config'
import ToastService from 'openvue/toastservice'
import Toast from 'openvue/toast'
import Aura from '@openvue/themes/aura'

import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { userWithPermissions } from '@/test-utils/factories'
import { useAdminSettingsStore } from '../../stores/adminSettingsStore'

import type {
  AdminMailSettings,
  AdminMailTemplate,
  AllAdminSettings,
  MailTemplateKindGroup,
} from '../../types/adminSettingsTypes'

// Mirrors AdminSettingsTabGeneral.locales.spec.ts / AdminSettingsTabMaintenance.spec.ts's
// mount/userWithPermissions/store-seeding pattern. The Mail tab's own fetch() is never
// exercised here (settings.mail is seeded directly); fetchMailTemplates()
// IS exercised, since it fires from onMounted and every template-status
// assertion depends on its result landing in store.mailTemplates.

const getMock = vi.fn<(url: string) => Promise<unknown>>()
const putMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>()
// Only exercised by a system-family kind's editor dialog opening (it fires
// a preview POST as soon as it mounts). Not asserted on here, but must
// resolve rather than be undefined so that open doesn't reject.
const postMock = vi
  .fn<() => Promise<unknown>>()
  .mockResolvedValue({ data: { subject: '', html: '' } })

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
    put: (url: string, payload: unknown) => putMock(url, payload),
    post: () => postMock(),
  },
}))

import AdminSettingsTabMail from '../AdminSettingsTabMail.vue'
import MailTemplateEditorDialog from '../MailTemplateEditorDialog.vue'

function makeMailSettings(overrides: Partial<AdminMailSettings> = {}): AdminMailSettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    enabled: true,
    host: 'smtp.example.com',
    port: 587,
    user: 'mailer',
    password_configured: true,
    from_address: 'noreply@example.com',
    from_display_name: '',
    reply_to: null,
    use_tls: true,
    use_ssl: false,
    verify_certificate: true,
    alert_recipients: [],
    send_limit_per_hour: 20,
    send_lock_minutes: 60,
    attachment_limit_mb: 10,
    ...overrides,
  }
}

// AdminMailTemplate is a bare kind x language row, no family/variables
// (those live once per kind, on MailTemplateKindGroup below). Mirrors the
// backend's AdminMailTemplateResponse exactly, see adminSettingsTypes.ts.
function makeEntry(overrides: Partial<AdminMailTemplate> = {}): AdminMailTemplate {
  return {
    id: 1,
    public_id: '22222222-2222-2222-2222-222222222222',
    kind: 'welcome',
    language: 'enGB',
    subject: 'Welcome',
    body: '<p>Welcome!</p>',
    configured: true,
    ...overrides,
  }
}

// GET /admin/settings/mail/templates -> { kinds: MailTemplateKindGroup[] },
// one group per kind carrying family/variables/default_subject plus that
// kind's language rows, never a flat list of rows.
function makeGroup(overrides: Partial<MailTemplateKindGroup> = {}): MailTemplateKindGroup {
  return {
    kind: 'welcome',
    family: 'system',
    variables: ['full_name', 'domain'],
    default_subject: 'Welcome to Glados',
    entries: [],
    ...overrides,
  }
}

async function mountTab(permissions: string[], mail: AdminMailSettings, groups: MailTemplateKindGroup[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  // Seeded directly rather than driven through fetch(): only `mail` is
  // under test, so the rest of AllAdminSettings would be dead weight.
  useAdminSettingsStore().settings = { mail } as unknown as AllAdminSettings

  const hostStore = useHostStore()
  hostStore.languages = ['enGB', 'deAT']
  hostStore.loaded = true

  getMock.mockResolvedValue({ data: { kinds: groups } })

  // AdminSettingsTabMail.vue renders no <Toast/> of its own (the real app's
  // is at the layout level), so it's mounted alongside here, the same as
  // AdminSettingsTabMaintenance.spec.ts does, giving a toast.add() call
  // somewhere to render into.
  const wrapper = mount(
    {
      components: { AdminSettingsTabMail, Toast },
      template: '<div><AdminSettingsTabMail /><Toast /></div>',
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

function saveButton(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (i18n.global.t('common.save') as string))!
}

function templateRow(wrapper: ReturnType<typeof mount>, kind: string) {
  const label = i18n.global.t(`adminSettings.mail.templates.${kind}.label`) as string
  return wrapper.findAll('.template-row').find((r) => r.text().includes(label))!
}

// DOMWrapper.findAllComponents() is typed `any` (see @vue/test-utils'
// domWrapper.d.ts), so callbacks over its result need an explicit parameter
// type to satisfy noImplicitAny.
type ComponentWrapperLike = { props: (key: string) => unknown }

function editButtonFor(wrapper: ReturnType<typeof mount>, kind: string) {
  const editLabel = i18n.global.t('adminSettings.mail.templates.edit') as string
  return templateRow(wrapper, kind)
    .findAllComponents({ name: 'Button' })
    .find((b: ComponentWrapperLike) => b.props('label') === editLabel)!
}

describe('AdminSettingsTabMail templates section', () => {
  beforeEach(() => {
    getMock.mockReset()
    putMock.mockReset()
    document.body.innerHTML = ''
  })

  it('fetches templates on mount and shows Provider + Templates section labels', async () => {
    const wrapper = await mountTab(['write:settings'], makeMailSettings(), [makeGroup()])

    expect(getMock).toHaveBeenCalledWith('/admin/settings/mail/templates')
    expect(wrapper.text()).toContain(i18n.global.t('adminSettings.mail.providerSection'))
    expect(wrapper.text()).toContain(i18n.global.t('adminSettings.mail.templatesSection'))

    wrapper.unmount()
  })

  it('shows the three template sub-groups', async () => {
    const wrapper = await mountTab(['write:settings'], makeMailSettings(), [])

    expect(wrapper.text()).toContain(i18n.global.t('adminSettings.mail.templates.groups.user'))
    expect(wrapper.text()).toContain(i18n.global.t('adminSettings.mail.templates.groups.supplier'))
    expect(wrapper.text()).toContain(i18n.global.t('adminSettings.mail.templates.groups.system'))

    wrapper.unmount()
  })

  // All twelve MailTemplateKind values render, grouped by family. A kind
  // needs only a TEMPLATE_ROWS entry, no dialog change, since
  // family/variables/configured are always read off the fetched row
  // itself.
  const KIND_GROUPS: Record<string, string[]> = {
    user: ['welcome', 'account_deactivated', 'permissions_changed', 'project_assigned', 'product_assigned'],
    supplier: ['request', 'order', 'order_canceled'],
    customer: ['meeting_notes'],
    system: ['notification_digest', 'test_mail', 'schedule_error', 'disk_space_warning'],
  }

  it('renders all twelve kinds, each in its own family sub-group', async () => {
    const wrapper = await mountTab(['write:settings'], makeMailSettings(), [])

    for (const [group, kinds] of Object.entries(KIND_GROUPS)) {
      const groupLabel = i18n.global.t(`adminSettings.mail.templates.groups.${group}`) as string
      for (const kind of kinds) {
        const row = templateRow(wrapper, kind)
        // The row exists at all (label/hint resolved, not a raw key path)...
        expect(row.text()).toContain(
          i18n.global.t(`adminSettings.mail.templates.${kind}.label`) as string,
        )
        // ...and sits inside its expected sub-group, not some other one:
        // walk up to the group's <template> block by checking every row of
        // that group appears after its group label and before the next one.
        const allText = wrapper.text()
        const groupIndex = allText.indexOf(groupLabel)
        const rowLabelIndex = allText.indexOf(
          i18n.global.t(`adminSettings.mail.templates.${kind}.label`) as string,
        )
        expect(rowLabelIndex).toBeGreaterThan(groupIndex)
      }
    }

    wrapper.unmount()
  })

  it('opens order_canceled as a supplier-family editor with the order variable chips', async () => {
    const orderVariables = [
      'order_number',
      'supplier',
      'note',
      'ordered_date',
      'expected_delivery',
      'total',
      'total_price',
      'user_full_name',
      'user_email',
    ]
    const wrapper = await mountTab(['write:settings'], makeMailSettings(), [
      makeGroup({
        kind: 'order_canceled',
        family: 'supplier',
        variables: orderVariables,
        entries: [
          makeEntry({ kind: 'order_canceled', language: 'enGB', configured: false, body: '' }),
          makeEntry({ kind: 'order_canceled', language: 'deAT', configured: false, body: '' }),
        ],
      }),
    ])

    await editButtonFor(wrapper, 'order_canceled').trigger('click')
    await flushPromises()

    const dialog = wrapper.findComponent(MailTemplateEditorDialog)
    expect(dialog.exists()).toBe(true)
    expect(dialog.props('kind')).toBe('order_canceled')
    expect(dialog.props('family')).toBe('supplier')
    expect(dialog.props('variables')).toEqual(orderVariables)

    wrapper.unmount()
  })

  it('shows a per-language status Tag colored by configured', async () => {
    const wrapper = await mountTab(['write:settings'], makeMailSettings(), [
      makeGroup({
        kind: 'welcome',
        entries: [
          makeEntry({ kind: 'welcome', language: 'enGB', configured: true }),
          makeEntry({ kind: 'welcome', language: 'deAT', configured: false, body: '' }),
        ],
      }),
    ])

    const tags = templateRow(wrapper, 'welcome').findAllComponents({ name: 'Tag' })
    expect(tags.map((t: ComponentWrapperLike) => t.props('value'))).toEqual(['EN', 'DE'])
    expect(tags[0]!.props('severity')).toBe('success')
    expect(tags[1]!.props('severity')).toBe('secondary')

    wrapper.unmount()
  })

  it('keeps Edit enabled without write:settings, but disables the toolbar Save', async () => {
    const wrapper = await mountTab([], makeMailSettings(), [makeGroup()])

    expect(saveButton(wrapper).attributes('disabled')).toBeDefined()
    expect(editButtonFor(wrapper, 'welcome').attributes('disabled')).toBeUndefined()

    wrapper.unmount()
  })

  it('shows the alert recipient controls disabled with the missing permission without write:settings', async () => {
    const wrapper = await mountTab([], makeMailSettings({ alert_recipients: ['ops@example.com'] }), [])

    expect(wrapper.get('.recipient-remove').attributes('disabled')).toBeDefined()
    const addRow = wrapper.get('.recipient-add-row')
    expect(addRow.get('input').attributes('disabled')).toBeDefined()
    expect(addRow.get('button').attributes('disabled')).toBeDefined()
    expect((addRow.element as HTMLElement & { $_ptooltipValue?: string }).$_ptooltipValue).toBe(
      'This needs the permission Write Settings.',
    )

    wrapper.unmount()
  })

  it('opens the editor dialog and PUTs only that kind on save', async () => {
    // PUT returns a single MailTemplateKindGroup, not a list and not
    // { templates: [...] }.
    putMock.mockResolvedValue({
      data: makeGroup({
        kind: 'welcome',
        entries: [
          makeEntry({ kind: 'welcome', language: 'enGB', subject: 'Hi', configured: true }),
        ],
      }),
    })
    const wrapper = await mountTab(['write:settings'], makeMailSettings(), [
      makeGroup({
        kind: 'welcome',
        entries: [
          makeEntry({ kind: 'welcome', language: 'enGB' }),
          makeEntry({ kind: 'welcome', language: 'deAT', configured: false, body: '' }),
        ],
      }),
    ])

    await editButtonFor(wrapper, 'welcome').trigger('click')
    await flushPromises()

    const dialog = wrapper.findComponent(MailTemplateEditorDialog)
    expect(dialog.exists()).toBe(true)
    expect(dialog.props('kind')).toBe('welcome')

    const dialogSaveButton = dialog
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === (i18n.global.t('common.save') as string))!
    await dialogSaveButton.trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith(
      '/admin/settings/mail/templates/welcome',
      expect.objectContaining({
        entries: expect.arrayContaining([
          expect.objectContaining({ language: 'enGB' }),
          expect.objectContaining({ language: 'deAT' }),
        ]),
      }),
    )

    wrapper.unmount()
  })

  it('rejects an invalid alert recipient without adding it', async () => {
    const wrapper = await mountTab(['write:settings'], makeMailSettings(), [])

    const emailInput = wrapper.find('input[type="email"]')
    await emailInput.setValue('not an email')
    await emailInput.trigger('keydown.enter')
    await flushPromises()

    expect(document.body.textContent).toContain(
      i18n.global.t('adminSettings.mail.invalidRecipient', { email: 'not an email' }),
    )
    expect(
      wrapper.findAll('.recipient-tag').some((tag) => tag.text().includes('not an email')),
    ).toBe(false)

    wrapper.unmount()
  })

  it('PUTs alert_recipients with the rest of the Provider form on Save', async () => {
    putMock.mockResolvedValue({ data: makeMailSettings({ alert_recipients: ['ops@example.com'] }) })
    const wrapper = await mountTab(['write:settings'], makeMailSettings(), [])

    const emailInput = wrapper.find('input[type="email"]')
    await emailInput.setValue('ops@example.com')
    await emailInput.trigger('keydown.enter')
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith(
      '/admin/settings/mail',
      expect.objectContaining({ alert_recipients: ['ops@example.com'] }),
    )

    wrapper.unmount()
  })

  it('reflects from_display_name/reply_to/send_limit_per_hour/send_lock_minutes from settings.mail', async () => {
    const wrapper = await mountTab(
      ['write:settings'],
      makeMailSettings({
        from_display_name: 'GLADOS',
        reply_to: 'support@example.com',
        send_limit_per_hour: 42,
        send_lock_minutes: 90,
      }),
      [],
    )

    const displayNameLabel = i18n.global.t('adminSettings.mail.fromDisplayName') as string
    const replyToLabel = i18n.global.t('adminSettings.mail.replyTo') as string
    const limitLabel = i18n.global.t('adminSettings.mail.sendLimitPerHour') as string
    const lockLabel = i18n.global.t('adminSettings.mail.sendLockMinutes') as string

    const fieldRow = (label: string) =>
      wrapper.findAll('.field-row').find((r) => r.text().includes(label))!

    expect(fieldRow(displayNameLabel).findComponent({ name: 'InputText' }).props('modelValue')).toBe(
      'GLADOS',
    )
    expect(fieldRow(replyToLabel).findComponent({ name: 'InputText' }).props('modelValue')).toBe(
      'support@example.com',
    )
    expect(fieldRow(limitLabel).findComponent({ name: 'InputNumber' }).props('modelValue')).toBe(42)
    expect(fieldRow(lockLabel).findComponent({ name: 'InputNumber' }).props('modelValue')).toBe(90)

    wrapper.unmount()
  })

  it('PUTs from_display_name/reply_to/send_limit_per_hour/send_lock_minutes with the rest of the form on Save', async () => {
    putMock.mockResolvedValue({ data: makeMailSettings() })
    const wrapper = await mountTab(['write:settings'], makeMailSettings(), [])

    const displayNameLabel = i18n.global.t('adminSettings.mail.fromDisplayName') as string
    const replyToLabel = i18n.global.t('adminSettings.mail.replyTo') as string
    const limitLabel = i18n.global.t('adminSettings.mail.sendLimitPerHour') as string
    const lockLabel = i18n.global.t('adminSettings.mail.sendLockMinutes') as string

    const fieldRow = (label: string) =>
      wrapper.findAll('.field-row').find((r) => r.text().includes(label))!

    await fieldRow(displayNameLabel)
      .findComponent({ name: 'InputText' })
      .vm.$emit('update:modelValue', 'GLADOS')
    await fieldRow(replyToLabel)
      .findComponent({ name: 'InputText' })
      .vm.$emit('update:modelValue', 'support@example.com')
    await fieldRow(limitLabel)
      .findComponent({ name: 'InputNumber' })
      .vm.$emit('update:modelValue', 42)
    await fieldRow(lockLabel)
      .findComponent({ name: 'InputNumber' })
      .vm.$emit('update:modelValue', 90)
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith(
      '/admin/settings/mail',
      expect.objectContaining({
        from_display_name: 'GLADOS',
        reply_to: 'support@example.com',
        send_limit_per_hour: 42,
        send_lock_minutes: 90,
      }),
    )

    wrapper.unmount()
  })

  it('shows the attachment limit and PUTs it with the rest of the form on Save', async () => {
    putMock.mockResolvedValue({ data: makeMailSettings() })
    const wrapper = await mountTab(['write:settings'], makeMailSettings({ attachment_limit_mb: 15 }), [])

    const limit = wrapper.get('[data-testid="mail-attachment-limit"]')
    expect(limit.findComponent({ name: 'InputNumber' }).props('modelValue')).toBe(15)
    expect(limit.findComponent({ name: 'InputNumber' }).props('max')).toBe(100)
    await limit.findComponent({ name: 'InputNumber' }).vm.$emit('update:modelValue', 25)
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith('/admin/settings/mail', expect.objectContaining({ attachment_limit_mb: 25 }))

    wrapper.unmount()
  })
})
