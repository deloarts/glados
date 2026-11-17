import { describe, it, expect } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { Permission } from '@/core/auth/permissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import type { UserResponse } from '@/core/types/userResponse'
import type { ProductResponse } from '../../types/productResponse'

import ProductFilesTab from '../ProductFilesTab.vue'

function makeProduct(overrides: Partial<ProductResponse> = {}): ProductResponse {
  return {
    edit_version: 0,
    id: 4,
    public_id: '11111111-1111-1111-1111-111111111111',
    product_number: 'PN-0004',
    customer_id: null,
    customer: null,
    description: null,
    is_active: true,
    archived: false,
    designated_user_id: 1,
    created: '2026-01-01T00:00:00Z',
    creator_id: 1,
    creator: null,
    designation: null,
    machine_type: null,
    installation_site: null,
    installation_location: null,
    planned_placing_on_market: null,
    legal_basis: null,
    plc_environment_id: null,
    contains_pneumatics: false,
    contains_hydraulics: false,
    contains_electrics: false,
    contains_robotics: false,
    ...overrides,
  }
}

function mountTab(userId: number, permissions: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = {
    id: userId,
    is_systemuser: false,
    permissions,
  } as unknown as UserResponse
  return mountWithApp(ProductFilesTab, {
    pinia,
    props: { product: makeProduct() },
    global: { stubs: { ItemImageSection: true } },
  })
}

describe('ProductFilesTab', () => {
  it('passes the product and its files store to the file section', () => {
    const wrapper = mountTab(2, [])

    const section = wrapper.findComponent({ name: 'ItemImageSection' })
    expect(section.props('itemId')).toBe(4)
    expect(section.props('i18nPrefix')).toBe('resources.products.files')
  })

  it.each([
    { name: 'a manager', userId: 2, permissions: [Permission.MANAGE_PROJECTS], canEdit: true },
    { name: 'the designated user', userId: 1, permissions: [], canEdit: true },
    { name: 'another writer', userId: 2, permissions: [Permission.WRITE_PROJECTS], canEdit: false },
  ])('lets $name edit files: $canEdit', ({ userId, permissions, canEdit }) => {
    const wrapper = mountTab(userId, permissions)

    expect(wrapper.findComponent({ name: 'ItemImageSection' }).props('canEdit')).toBe(canEdit)
  })
})
