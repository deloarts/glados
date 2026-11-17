import { describe, it, expect } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { userWithPermissions } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { Permission } from '@/core/auth/permissions'

import FabricationMethodManagementView from '../FabricationMethodManagementView.vue'

// Smoke spec for the View tier assembled from ManagementCrudShell;
// the Table (and its context-menu/detail/delete wiring) already has its
// own thorough spec, so this only proves the shell is wired correctly: the
// create button's label/permission gate, and that clicking it opens the
// feature's own create dialog. Table and FormDialog are stubbed so this
// spec needs no API mocking.
function mountView(permissions: string[] = []) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)

  return mountWithApp(FabricationMethodManagementView, {
    pinia,
    global: {
      stubs: {
        FabricationMethodManagementTable: true,
        FabricationMethodFormDialog: true,
      },
    },
  })
}

describe('FabricationMethodManagementView', () => {
  it('gates the create button on write:fabrication_methods and renders the table', () => {
    const withoutPermission = mountView([])
    const disabledButton = withoutPermission
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('icon') === 'mdi mdi-plus')!
    expect(disabledButton.attributes('disabled')).toBeDefined()
    withoutPermission.unmount()

    const withPermission = mountView([Permission.WRITE_FABRICATION_METHODS])
    const enabledButton = withPermission
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('icon') === 'mdi mdi-plus')!
    expect(enabledButton.attributes('disabled')).toBeUndefined()
    expect(
      withPermission.findComponent({ name: 'FabricationMethodManagementTable' }).exists(),
    ).toBe(true)
    withPermission.unmount()
  })

  it('opens the create form dialog when the create button is clicked', async () => {
    const wrapper = mountView([Permission.WRITE_FABRICATION_METHODS])
    const button = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('icon') === 'mdi mdi-plus')!

    await button.trigger('click')

    expect(wrapper.findComponent({ name: 'FabricationMethodFormDialog' }).props('visible')).toBe(
      true,
    )
    wrapper.unmount()
  })
})
