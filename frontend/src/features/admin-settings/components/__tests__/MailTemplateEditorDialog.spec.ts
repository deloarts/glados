import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, DOMWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { userWithPermissions } from '@/test-utils/factories'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { TABLE_COLUMN_KEYS } from '@/shared/order-mail'

import type { AdminMailTemplate, MailTemplateFamily, MailTemplateKind } from '../../types/adminSettingsTypes'

// OpenVue's Dialog teleports its content to document.body (not a
// descendant of the wrapper's own root element), and needs a tick after
// mount (or after a visible transition) before that content actually
// exists, see SourceItemDemandDetailDialog.spec.ts's identical caveat.
// So: every assertion here queries `document.body` directly rather than
// `wrapper.find()`/`wrapper.text()`, and every mount/interaction is
// followed by `await flushPromises()` before reading the DOM.
// `findComponent`/`findAllComponents`/`emitted()` are unaffected (they walk
// the component tree and event log, not physical DOM position), so those
// still go through `wrapper`.

const postMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>()
const putMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    post: (url: string, payload: unknown) => postMock(url, payload),
    put: (url: string, payload: unknown) => putMock(url, payload),
  },
}))

import MailTemplateEditorDialog from '../MailTemplateEditorDialog.vue'

// AdminMailTemplate is a bare kind x language row, with no family/variables
// (those are the dialog's own props, driven by the group, not per-entry).
function makeEntry(overrides: Partial<AdminMailTemplate> = {}): AdminMailTemplate {
  return {
    id: 1,
    public_id: '22222222-2222-2222-2222-222222222222',
    kind: 'welcome',
    language: 'enGB',
    subject: 'Welcome',
    body: 'Hello {{ full_name }}',
    configured: true,
    ...overrides,
  }
}

// Mounted closed, then opened, same convention as WebhookFormDialog.spec.ts
// ("the dialog only populates its form from watch(visible, ...), which
// fires on a false -> true transition, not on an initial visible: true
// mount"), and it also matches how AdminSettingsTabMail.vue actually uses
// this dialog: always mounted, toggled via v-model:visible.
async function mountDialog(options: {
  kind?: MailTemplateKind
  family?: MailTemplateFamily
  variables?: string[]
  entries?: AdminMailTemplate[]
  permissions?: string[]
}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(options.permissions ?? ['write:settings'])

  const family = options.family ?? 'system'
  const kind = options.kind ?? 'welcome'

  const wrapper = mountWithApp(MailTemplateEditorDialog, {
    pinia,
    attachTo: document.body,
    props: {
      visible: false,
      kind,
      family,
      variables: options.variables ?? ['full_name', 'domain'],
      entries: options.entries ?? [makeEntry({ kind })],
    },
  })
  await flushPromises()
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

function body() {
  return document.body
}

describe('MailTemplateEditorDialog', () => {
  beforeEach(() => {
    postMock.mockReset()
    putMock.mockReset()
    document.body.innerHTML = ''
  })

  it('renders one variable chip per entry in props.variables', async () => {
    const wrapper = await mountDialog({ variables: ['full_name', 'domain', 'custom_var'] })

    const chipValues = Array.from(body().querySelectorAll('.var-chip')).map(
      (c) => c.textContent,
    )
    expect(chipValues).toEqual(
      expect.arrayContaining(['{{ full_name }}', '{{ domain }}', '{{ custom_var }}']),
    )

    wrapper.unmount()
  })

  it('hides the table-column chips for a system-family template', async () => {
    const wrapper = await mountDialog({ family: 'system' })

    expect(body().textContent).not.toContain(
      i18n.global.t('adminSettings.mail.templates.editor.tableColumns'),
    )

    wrapper.unmount()
  })

  it('shows table-column chips for a supplier-family template', async () => {
    const wrapper = await mountDialog({
      kind: 'order',
      family: 'supplier',
      variables: ['order_number'],
    })

    expect(body().textContent).toContain(
      i18n.global.t('adminSettings.mail.templates.editor.tableColumns'),
    )
    const chipValues = Array.from(body().querySelectorAll('.var-chip')).map(
      (c) => c.textContent,
    )
    expect(chipValues).toEqual(expect.arrayContaining([...TABLE_COLUMN_KEYS]))

    wrapper.unmount()
  })

  it('renders a supplier-family preview synchronously (no network call)', async () => {
    const wrapper = await mountDialog({
      kind: 'order',
      family: 'supplier',
      variables: ['order_number'],
      entries: [
        makeEntry({
          kind: 'order',
          body: 'Order {{ order_number }}',
        }),
      ],
    })

    expect(body().querySelector('.preview-content')!.textContent).toContain('ORD-2024-001')
    expect(postMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('renders a system-family preview via a server-side preview call into a sandboxed iframe', async () => {
    postMock.mockResolvedValue({ data: { subject: 'Rendered subject', html: '<p>Rendered</p>' } })
    const wrapper = await mountDialog({
      kind: 'welcome',
      family: 'system',
      entries: [makeEntry({ kind: 'welcome', body: 'Hello {{ full_name }}' })],
    })
    await flushPromises()

    // Exact match, not objectContaining: proves `language` is NOT sent at
    // all (the preview renders against the kind's server-side sample
    // context, never a specific recipient language).
    expect(postMock).toHaveBeenCalledWith('/admin/settings/mail/templates/welcome/preview', {
      subject: 'Welcome',
      body: 'Hello {{ full_name }}',
    })
    const iframe = body().querySelector('iframe')
    expect(iframe).not.toBeNull()
    expect(iframe!.getAttribute('srcdoc')).toBe('<p>Rendered</p>')
    // No allow-scripts/allow-same-origin (or anything else) on the sandbox.
    expect(iframe!.getAttribute('sandbox')).toBe('')

    wrapper.unmount()
  })

  it('shows the preview error inline on a 400 from the preview endpoint, instead of an iframe', async () => {
    postMock.mockRejectedValue({
      isAxiosError: true,
      response: { status: 400, data: { detail: 'Unexpected end of template' } },
    })
    const wrapper = await mountDialog({ kind: 'welcome', family: 'system' })
    await flushPromises()

    expect(body().textContent).toContain('Unexpected end of template')
    expect(body().querySelector('iframe')).toBeNull()

    wrapper.unmount()
  })

  it('preserves each language draft when switching, rather than losing unsaved edits', async () => {
    const wrapper = await mountDialog({
      kind: 'order',
      family: 'supplier',
      variables: ['order_number'],
      entries: [
        makeEntry({ kind: 'order', language: 'enGB', body: 'EN original' }),
        makeEntry({ kind: 'order', language: 'deAT', body: 'DE original' }),
      ],
    })

    const textarea = () => body().querySelector('textarea.html-textarea') as HTMLTextAreaElement

    await new DOMWrapper(textarea()).setValue('EN edited')

    await wrapper.findComponent({ name: 'SelectButton' }).vm.$emit('update:modelValue', 'deAT')
    await flushPromises()
    expect(textarea().value).toBe('DE original')

    await new DOMWrapper(textarea()).setValue('DE edited')
    await wrapper.findComponent({ name: 'SelectButton' }).vm.$emit('update:modelValue', 'enGB')
    await flushPromises()
    expect(textarea().value).toBe('EN edited')

    wrapper.unmount()
  })

  it('disables Save without write:settings', async () => {
    const wrapper = await mountDialog({ permissions: [] })

    const save = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === (i18n.global.t('common.save') as string))!
    // Button has no declared `disabled` prop, it derives disabled-ness
    // from $attrs.disabled at render time, so assert the rendered DOM
    // attribute rather than a component prop (see
    // AdminSettingsTabMaintenance.spec.ts's saveButton()).
    expect(save.attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  it('saves every language via a single kind-scoped PUT and closes', async () => {
    // PUT returns a single MailTemplateKindGroup, not a list and not
    // { templates: [...] }.
    putMock.mockResolvedValue({
      data: {
        kind: 'welcome',
        family: 'system',
        variables: ['full_name', 'domain'],
        default_subject: 'Welcome to Glados',
        entries: [makeEntry({ subject: 'Edited' })],
      },
    })
    const wrapper = await mountDialog({
      kind: 'welcome',
      family: 'system',
      entries: [
        makeEntry({ kind: 'welcome', language: 'enGB', subject: 'EN subj' }),
        makeEntry({ kind: 'welcome', language: 'deAT', subject: 'DE subj' }),
      ],
    })

    const save = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === (i18n.global.t('common.save') as string))!
    await save.trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith(
      '/admin/settings/mail/templates/welcome',
      expect.objectContaining({
        entries: expect.arrayContaining([
          expect.objectContaining({ language: 'enGB', subject: 'EN subj' }),
          expect.objectContaining({ language: 'deAT', subject: 'DE subj' }),
        ]),
      }),
    )
    expect(wrapper.emitted('update:visible')?.at(-1)).toEqual([false])

    wrapper.unmount()
  })
})
