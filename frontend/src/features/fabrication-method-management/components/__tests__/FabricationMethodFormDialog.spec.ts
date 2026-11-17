import { describe, it, expect, vi } from 'vitest'
import { flushPromises, DOMWrapper } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'

const postMock = vi
  .fn<(url: string, payload: Record<string, unknown>) => Promise<unknown>>()
  .mockResolvedValue({ data: {} })
const putMock = vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} })

function makeSupplierListResponse(overrides: Record<string, unknown> = {}) {
  return {
    data: {
      items: [
        {
          id: 9,
          public_id: '99999999-9999-9999-9999-999999999999',
          created: '2026-01-01',
          changed: '2026-01-01T00:00:00Z',
          archived: false,
          name: 'Acme Anodizing',
          legal_name: null,
          vat_id: null,
          level: 'B',
          capability_ids: [],
          capabilities: [],
          article_group_ids: [],
          article_groups: [],
          street: null,
          city: null,
          country: null,
          postal_code: null,
          email: null,
          phone: null,
          weblink: null,
          order_email: null,
          order_language: null,
          order_template: null,
          request_email: null,
          request_language: null,
          request_template: null,
          creator_id: 1,
          creator: null,
          ...overrides,
        },
      ],
      total: 1,
      limit: 1000,
      skip: 0,
    },
  }
}

const getMock = vi
  .fn<(url: string, config?: { params?: Record<string, unknown> }) => Promise<unknown>>()
  .mockResolvedValue(makeSupplierListResponse())

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: { params?: Record<string, unknown> }) => getMock(url, config),
    post: (url: string, payload: Record<string, unknown>) => postMock(url, payload),
    put: (...args: unknown[]) => putMock(...(args as [])),
  },
}))

import FabricationMethodFormDialog from '../FabricationMethodFormDialog.vue'
import type { FabricationMethodResponse } from '@/features/fabrication-methods'

const method: FabricationMethodResponse = {
  id: 1,
  public_id: '11111111-1111-1111-1111-111111111111',
  created: '2026-07-01',
  changed: '2026-07-01T00:00:00Z',
  changed_by: null,
  changed_by_id: null,
  name: { enGB: 'Milling' },
  description: { enGB: '' },
  label_color: '#6366f1',
  label_font_color: '#ffffff',
  requires_machine: true,
  required_external: true,
  default_supplier_id: 9,
  lead_time_days: 5,
  default_for_assemblies: false,
  archived: true,
  creator_id: 1,
  creator: null,
}

// The name is entered per language; the default language's input is the
// one a create needs, and the test host offers only that language.
const NAME_INPUT = '[data-testid="localized-text-enGB"]'

describe('FabricationMethodFormDialog', () => {
  it('renders in create mode without errors when opened', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountWithApp(FabricationMethodFormDialog, {
      attachTo: document.body,
      props: { visible: true, method: undefined },
    })

    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])

    wrapper.unmount()
  })

  it('renders in edit mode pre-filled with the method without errors', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountWithApp(FabricationMethodFormDialog, {
      attachTo: document.body,
      // Mount closed first, then open: the dialog only populates its form
      // from `watch(visible, ...)`, which fires on a false -> true
      // transition, not on an initial `visible: true` mount.
      props: { visible: false, method },
    })

    await flushPromises()

    await wrapper.setProps({ visible: true })
    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])

    // Dialog content is teleported to document.body, outside the wrapper's
    // own root element, so query the document directly rather than
    // wrapper.find().
    const nameInput = document.body.querySelector<HTMLInputElement>(NAME_INPUT)
    expect(nameInput?.value).toBe('Milling')

    const requiredExternalCheckbox =
      document.body.querySelector<HTMLInputElement>('#fm-required-external')
    expect(requiredExternalCheckbox?.checked).toBe(true)

    // Archiving is action-driven (Archive/Restore), not settable from this
    // form, so the form has no archived checkbox.
    expect(document.body.querySelector('#fm-archived')).toBeNull()

    wrapper.unmount()
  })

  it('submits default_for_assemblies on create once checked', async () => {
    postMock.mockClear()

    const wrapper = mountWithApp(FabricationMethodFormDialog, {
      attachTo: document.body,
      props: { visible: true, method: undefined },
    })

    await flushPromises()
    await flushPromises()

    await new DOMWrapper(document.body.querySelector(NAME_INPUT)!).setValue('Assembly')
    await new DOMWrapper(document.body.querySelector('#fm-default-for-assemblies')!).setValue(true)
    await flushPromises()

    await new DOMWrapper(document.body.querySelector('form.method-form')!).trigger('submit')
    await flushPromises()

    expect(postMock).toHaveBeenCalledTimes(1)
    const [, payload] = postMock.mock.calls[0]!
    expect(payload.default_for_assemblies).toBe(true)

    wrapper.unmount()
  })

  // The backend rejects an archived method as the default for assemblies,
  // and the fixture method is archived.
  it('disables the default for assemblies checkbox for an archived method', async () => {
    const wrapper = mountWithApp(FabricationMethodFormDialog, {
      attachTo: document.body,
      props: { visible: false, method },
    })

    await flushPromises()
    await wrapper.setProps({ visible: true })
    await flushPromises()
    await flushPromises()

    const checkbox = document.body.querySelector<HTMLInputElement>('#fm-default-for-assemblies')
    expect(checkbox?.disabled).toBe(true)

    wrapper.unmount()
  })

  it('submits required_external and default_supplier_id on create', async () => {
    postMock.mockClear()

    const wrapper = mountWithApp(FabricationMethodFormDialog, {
      attachTo: document.body,
      props: { visible: true, method: undefined },
    })

    await flushPromises()
    await flushPromises()

    await new DOMWrapper(document.body.querySelector(NAME_INPUT)!).setValue('Anodizing')
    await new DOMWrapper(document.body.querySelector('#fm-required-external')!).setValue(true)
    await flushPromises()

    await new DOMWrapper(document.body.querySelector('form.method-form')!).trigger('submit')
    await flushPromises()

    expect(postMock).toHaveBeenCalledTimes(1)
    const [, payload] = postMock.mock.calls[0]!
    expect(payload.name).toEqual({ enGB: 'Anodizing' })
    expect(payload.required_external).toBe(true)
    expect(payload.archived).toBeUndefined()
    expect(payload.default_supplier_id).toBe(null)
    expect(payload.lead_time_days).toBe(null)

    wrapper.unmount()
  })

  // The lead-time field only appears once the method is (or might become)
  // external work, or a value is already set; see showLeadTimeField.
  it('shows the lead time field only once required_external is checked, or a value is already set', async () => {
    const wrapper = mountWithApp(FabricationMethodFormDialog, {
      attachTo: document.body,
      props: { visible: true, method: undefined },
    })

    await flushPromises()
    await flushPromises()

    expect(document.body.querySelector('#fm-lead-time-days')).toBeNull()

    await new DOMWrapper(document.body.querySelector('#fm-required-external')!).setValue(true)
    await flushPromises()

    expect(document.body.querySelector('#fm-lead-time-days')).not.toBeNull()

    wrapper.unmount()

    // Edit mode: the fixture method has required_external=true and
    // lead_time_days=5, so the field renders pre-filled without needing
    // any interaction.
    const editWrapper = mountWithApp(FabricationMethodFormDialog, {
      attachTo: document.body,
      props: { visible: false, method },
    })
    await flushPromises()
    await editWrapper.setProps({ visible: true })
    await flushPromises()
    await flushPromises()

    const leadTimeInput = document.body.querySelector<HTMLInputElement>('#fm-lead-time-days')
    expect(leadTimeInput?.value).toBe('5')

    editWrapper.unmount()
  })

  // Referencing an already-archived supplier as a method's default supplier
  // is allowed; see useArchivableOptions.ts. The suppliers fetch
  // requests every row regardless of archived state, and an archived
  // current value is flagged.
  it('requests archived suppliers too, and flags an archived default supplier with the tag and warning', async () => {
    getMock.mockClear()
    getMock.mockResolvedValueOnce(makeSupplierListResponse({ archived: true }))

    const wrapper = mountWithApp(FabricationMethodFormDialog, {
      attachTo: document.body,
      props: { visible: false, method: { ...method, default_supplier_id: 9 } },
    })

    await flushPromises()
    await wrapper.setProps({ visible: true })
    await flushPromises()
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith(
      '/suppliers/',
      expect.objectContaining({ params: expect.objectContaining({ include_archived: true }) }),
    )

    // Dialog content is teleported to document.body; query there, not the
    // wrapper's own root (see other tests in this file for the same caveat).
    expect(document.body.textContent).toContain(i18n.global.t('common.archivedTag'))
    expect(document.body.textContent).toContain(i18n.global.t('common.archivedSelectionWarning'))

    wrapper.unmount()
  })
})
