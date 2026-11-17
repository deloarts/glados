import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { answerConfirmations } from '@/test-utils/confirmations'
import { i18n } from '@/core/i18n'
import { makeContact } from './contactFixtures'
import type { ContactCreateRequest, ContactUpdateRequest } from '../types/contactRequest'
import type { ContactResponse } from '../types/contactResponse'

const granted = new Set<string>()
vi.mock('@/core/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: (permission: string) => granted.has(permission) }),
}))

const createMock = vi.fn<(body: ContactCreateRequest) => Promise<ContactResponse>>()
const updateMock = vi.fn<(id: number, body: ContactUpdateRequest) => Promise<ContactResponse>>()
const anonymiseMock = vi.fn<(id: number) => Promise<ContactResponse>>()
vi.mock('../api/contactsApi', () => ({
  createContact: (body: ContactCreateRequest) => createMock(body),
  updateContact: (id: number, body: ContactUpdateRequest) => updateMock(id, body),
  anonymiseContact: (id: number) => anonymiseMock(id),
  archiveContact: vi.fn<() => Promise<void>>(),
  restoreContact: vi.fn<() => Promise<void>>(),
  getContactUsage: async () => [],
}))
vi.mock('../api/organisationLookup', () => ({
  fetchCustomerOptions: async () => [],
  fetchCustomerOptionsByIds: async () => [],
  fetchSupplierOptions: async () => [{ id: 3, label: 'Pneumatik Hypothetical' }],
  fetchSupplierOptionsByIds: async () => [{ id: 3, label: 'Pneumatik Hypothetical' }],
}))

import ContactFormDialog from '../components/ContactFormDialog.vue'

let wrapper: VueWrapper | null = null

async function open(props: Record<string, unknown> = {}) {
  wrapper = mountWithApp(ContactFormDialog, { attachTo: document.body, props: { visible: false, ...props } })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

function byTestId<T extends HTMLElement = HTMLElement>(id: string): T | null {
  return document.body.querySelector<T>(`[data-testid="${id}"]`)
}

async function type(id: string, value: string): Promise<void> {
  const input = byTestId<HTMLInputElement>(id)!
  input.value = value
  input.dispatchEvent(new Event('input'))
  await flushPromises()
}

beforeEach(() => {
  granted.clear()
  granted.add('read:contacts')
  granted.add('write:contacts')
  createMock.mockReset()
  updateMock.mockReset()
  anonymiseMock.mockReset()
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.body.innerHTML = ''
})

describe('ContactFormDialog', () => {
  it('creates a contact of the given customer without mail flags', async () => {
    createMock.mockResolvedValue(makeContact({ supplier_id: null, customer_id: 2 }))
    await open({ customerId: 2 })

    await type('contact-name', '  Thomas Muster ')
    await type('contact-email', 't.muster@muster.example')
    byTestId('contact-save')!.click()
    await flushPromises()

    expect(createMock).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Thomas Muster',
        email: 't.muster@muster.example',
        customer_id: 2,
        supplier_id: null,
        receives_request_mails: false,
        receives_order_mails: false,
      }),
    )
    expect(wrapper!.emitted('saved')).toHaveLength(1)
  })

  it('refuses to save without a name', async () => {
    await open()

    byTestId('contact-save')!.click()
    await flushPromises()

    expect(createMock).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain(i18n.global.t('contacts.errors.required'))
  })

  it('refuses to save a supplier contact without the supplier', async () => {
    await open({ contact: makeContact({ supplier_id: null }) })
    await flushPromises()
    const kind = wrapper!.findComponent({ name: 'Select' })
    kind.vm.$emit('update:modelValue', 'supplier')
    await flushPromises()

    byTestId('contact-save')!.click()
    await flushPromises()

    expect(updateMock).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain(i18n.global.t('contacts.errors.supplierRequired'))
  })

  it('sends the edit version and keeps the flags of a supplier contact', async () => {
    const contact = makeContact()
    updateMock.mockResolvedValue(contact)
    await open({ contact })

    expect(byTestId('contact-request-mails')).not.toBeNull()
    byTestId('contact-save')!.click()
    await flushPromises()

    expect(updateMock).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        supplier_id: 3,
        receives_request_mails: true,
        receives_order_mails: false,
        expected_edit_version: 2,
      }),
    )
  })

  it('stays visible but disabled without write:contacts and names the permission', async () => {
    granted.delete('write:contacts')
    await open({ contact: makeContact() })

    expect(byTestId<HTMLButtonElement>('contact-save')!.disabled).toBe(true)
    expect(byTestId<HTMLButtonElement>('contact-anonymise')!.disabled).toBe(true)
    expect(document.body.textContent).toContain(i18n.global.t('contacts.readOnly'))
  })

  it('anonymises after the confirmation', async () => {
    const confirmations = answerConfirmations('accept')
    anonymiseMock.mockResolvedValue(makeContact({ name: '', anonymised_at: '2026-11-10T09:00:00Z' }))
    await open({ contact: makeContact() })

    byTestId('contact-anonymise')!.click()
    await flushPromises()

    expect(confirmations.asked).toHaveLength(1)
    expect(anonymiseMock).toHaveBeenCalledWith(7)
    expect(wrapper!.emitted('saved')).toHaveLength(1)
    confirmations.stop()
  })
})
