import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { makeContact } from './contactFixtures'
import type { ContactFilterParams, ContactUpdateRequest } from '../types/contactRequest'
import type { ContactResponse } from '../types/contactResponse'
import type { PageResponse } from '@/core/api/types'

const granted = new Set<string>()
vi.mock('@/core/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: (permission: string) => granted.has(permission) }),
}))

const getContactsMock = vi.fn<(params?: ContactFilterParams) => Promise<PageResponse<ContactResponse>>>()
const updateMock = vi.fn<(id: number, body: ContactUpdateRequest) => Promise<ContactResponse>>()
vi.mock('../api/contactsApi', () => ({
  getContacts: (params?: ContactFilterParams) => getContactsMock(params),
  updateContact: (id: number, body: ContactUpdateRequest) => updateMock(id, body),
  getContactUsage: async () => [],
}))

import OrganisationContactsSection from '../components/OrganisationContactsSection.vue'

function mountSection(props: { kind: 'customer' | 'supplier'; organisationId: number | null }) {
  return mountWithApp(OrganisationContactsSection, {
    props,
    global: { directives: { tooltip: Tooltip } },
  })
}

beforeEach(() => {
  granted.clear()
  granted.add('read:contacts')
  granted.add('write:contacts')
  getContactsMock.mockReset()
  updateMock.mockReset()
  getContactsMock.mockResolvedValue({ items: [makeContact()], total: 1, limit: 100, skip: 0 })
})

describe('OrganisationContactsSection', () => {
  it('lists the supplier contacts and saves a mail flag', async () => {
    updateMock.mockResolvedValue(makeContact({ receives_order_mails: true }))
    const wrapper = mountSection({ kind: 'supplier', organisationId: 3 })
    await flushPromises()

    expect(getContactsMock).toHaveBeenCalledWith(expect.objectContaining({ supplier_id: 3 }))
    expect(wrapper.text()).toContain('Karin Hypothetical')

    const orderSwitch = wrapper.find('[data-testid="organisation-contact-order-mails"] input')
    await orderSwitch.setValue(true)
    await flushPromises()

    expect(updateMock).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        receives_request_mails: true,
        receives_order_mails: true,
        expected_edit_version: 2,
      }),
    )
  })

  it('asks to save a new organisation first', async () => {
    const wrapper = mountSection({ kind: 'customer', organisationId: null })
    await flushPromises()

    expect(getContactsMock).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain(i18n.global.t('contacts.organisationSection.saveCustomerFirst'))
  })

  it('says why it is empty without read:contacts and loads nothing', async () => {
    granted.clear()
    const wrapper = mountSection({ kind: 'customer', organisationId: 2 })
    await flushPromises()

    expect(getContactsMock).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="organisation-contacts-no-access"]').exists()).toBe(true)
  })

  it('keeps New Contact and the switches visible but disabled without write:contacts', async () => {
    granted.delete('write:contacts')
    const wrapper = mountSection({ kind: 'supplier', organisationId: 3 })
    await flushPromises()

    expect(wrapper.get('[data-testid="organisation-contacts-new"]').attributes('disabled')).toBeDefined()
    expect(
      wrapper.get('[data-testid="organisation-contact-order-mails"] input').attributes('disabled'),
    ).toBeDefined()
  })
})
