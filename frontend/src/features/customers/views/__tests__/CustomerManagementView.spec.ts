import { describe, it, expect } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { userWithPermissions } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { Permission } from '@/core/auth/permissions'

import CustomerManagementView from '../CustomerManagementView.vue'
import { useCustomersStore } from '../../stores/customersStore'

function mountView(permissions: string[] = []) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)

  return { pinia, wrapper: mountWithApp(CustomerManagementView, {
    pinia,
    global: {
      stubs: {
        CustomerManagementTable: true,
        CustomerFormDialog: true,
      },
    },
  }) }
}

describe('CustomerManagementView', () => {
  it('renders the management table', () => {
    const { wrapper } = mountView()

    expect(wrapper.findComponent({ name: 'PageLayout' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'CustomerManagementTable' }).exists()).toBe(true)

    wrapper.unmount()
  })

  // The create button is gated on write:projects rather than a customer-specific
  // permission. The test asserts the code's actual gate rather than the one
  // the permission name implies.
  it('gates the create button on write:projects', () => {
    const { wrapper: withoutPermission } = mountView([])
    const disabledButton = withoutPermission
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('icon') === 'mdi mdi-plus')!
    expect(disabledButton.attributes('disabled')).toBeDefined()
    withoutPermission.unmount()

    const { wrapper: withPermission } = mountView([Permission.WRITE_PROJECTS])
    const enabledButton = withPermission
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('icon') === 'mdi mdi-plus')!
    expect(enabledButton.attributes('disabled')).toBeUndefined()
    withPermission.unmount()
  })

  it('opens the create form dialog when the create button is clicked', async () => {
    const { wrapper } = mountView([Permission.WRITE_PROJECTS])
    const button = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('icon') === 'mdi mdi-plus')!

    await button.trigger('click')

    expect(wrapper.findComponent({ name: 'CustomerFormDialog' }).props('visible')).toBe(true)

    wrapper.unmount()
  })

  it('offers both sort-by and group-by menus, and binds the search field to store.search', async () => {
    const { wrapper } = mountView([Permission.WRITE_PROJECTS])

    const viewsBar = wrapper.findComponent({ name: 'ViewsBar' })
    expect(viewsBar.props('sortByItems')).toHaveLength(6)
    expect(viewsBar.props('groupByItems')).toHaveLength(2)

    await viewsBar.vm.$emit('update:search', 'acme corp')

    expect(useCustomersStore().search).toBe('acme corp')

    wrapper.unmount()
  })
})
