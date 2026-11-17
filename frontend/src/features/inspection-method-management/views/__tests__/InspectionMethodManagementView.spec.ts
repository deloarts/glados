import { describe, it, expect } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { userWithPermissions } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { Permission } from '@/core/auth/permissions'

import InspectionMethodManagementView from '../InspectionMethodManagementView.vue'

// Smoke spec for the View tier assembled from ManagementCrudShell. The Table
// and its context-menu/detail/delete wiring already have their own thorough
// spec, so this only verifies the shell wiring: create button label/permission
// gate and dialog open. Table and FormDialog are stubbed.
function mountView(permissions: string[] = []) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)

  return mountWithApp(InspectionMethodManagementView, {
    pinia,
    global: {
      stubs: {
        InspectionMethodManagementTable: true,
        InspectionMethodFormDialog: true,
      },
    },
  })
}

describe('InspectionMethodManagementView', () => {
  it('gates the create button on write:inspection_methods and renders the table', () => {
    const withoutPermission = mountView([])
    const disabledButton = withoutPermission
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('icon') === 'mdi mdi-plus')!
    expect(disabledButton.attributes('disabled')).toBeDefined()
    withoutPermission.unmount()

    const withPermission = mountView([Permission.WRITE_INSPECTION_METHODS])
    const enabledButton = withPermission
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('icon') === 'mdi mdi-plus')!
    expect(enabledButton.attributes('disabled')).toBeUndefined()
    expect(
      withPermission.findComponent({ name: 'InspectionMethodManagementTable' }).exists(),
    ).toBe(true)
    withPermission.unmount()
  })

  it('opens the create form dialog when the create button is clicked', async () => {
    const wrapper = mountView([Permission.WRITE_INSPECTION_METHODS])
    const button = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('icon') === 'mdi mdi-plus')!

    await button.trigger('click')

    expect(wrapper.findComponent({ name: 'InspectionMethodFormDialog' }).props('visible')).toBe(
      true,
    )
    wrapper.unmount()
  })
})
