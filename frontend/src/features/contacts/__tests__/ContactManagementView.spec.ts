import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeContact } from './contactFixtures'
import type { ContactFilterParams } from '../types/contactRequest'
import type { ContactResponse } from '../types/contactResponse'
import type { PageResponse } from '@/core/api/types'

const granted = new Set<string>()
vi.mock('@/core/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: (permission: string) => granted.has(permission) }),
}))

const getContactsMock = vi.fn<(params?: ContactFilterParams) => Promise<PageResponse<ContactResponse>>>()
vi.mock('../api/contactsApi', () => ({
  getContacts: (params?: ContactFilterParams) => getContactsMock(params),
  getContact: vi.fn<() => Promise<void>>(),
  getContactUsage: async (ids: number[]) =>
    ids.map((id) => ({
      contact_id: id,
      products: [{ owner: 'product', id: 4, number: 'P-031', receives_meeting_notes: true }],
      projects: [],
      meetings: [{ id: 21, meeting_number: 'MTG-26-0021', name: 'Kick-off' }],
    })),
  createContact: vi.fn<() => Promise<void>>(),
  updateContact: vi.fn<() => Promise<void>>(),
  archiveContact: vi.fn<() => Promise<void>>(),
  restoreContact: vi.fn<() => Promise<void>>(),
}))

import ContactManagementView from '../views/ContactManagementView.vue'

function mountView() {
  const router = createRouter({
    history: createWebHistory(),
    routes: [{ path: '/resources/:tab?', component: ContactManagementView }],
  })
  void router.push('/resources/contacts')
  return mountWithApp(ContactManagementView, {
    global: { plugins: [router], directives: { tooltip: Tooltip } },
  })
}

beforeEach(() => {
  granted.clear()
  getContactsMock.mockReset()
  getContactsMock.mockResolvedValue({ items: [makeContact()], total: 1, limit: 20, skip: 0 })
})

describe('ContactManagementView', () => {
  it('lists the contacts with their organisation and where they are used', async () => {
    granted.add('read:contacts')
    const wrapper = mountView()
    await flushPromises()

    const table = wrapper.get('[data-testid="contacts-table"]')
    expect(table.text()).toContain('Karin Hypothetical')
    expect(table.text()).toContain('Pneumatik Hypothetical')
    expect(table.text()).toContain('P-031')
    expect(table.text()).toContain('MTG-26-0021')
    expect(wrapper.get('[data-testid="management-create"]').attributes('disabled')).toBeDefined()
  })

  it('loads nothing without read:contacts and names the missing permission', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(getContactsMock).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="contacts-table"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Read Contacts')
  })
})
