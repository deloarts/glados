import { describe, it, expect } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { userWithPermissions } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { Permission } from '@/core/auth/permissions'

import SourceItemTypeManagementView from '../SourceItemTypeManagementView.vue'

// Smoke spec for the View tier assembled from ManagementCrudShell. The
// Table (and its context-menu/detail/delete wiring) already has its own
// thorough spec, so this only proves the shell is wired correctly: create
// button label/permission gate and form-dialog opening.
function mountView(permissions: string[] = []) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)

  return mountWithApp(SourceItemTypeManagementView, {
    pinia,
    global: {
      stubs: {
        SourceItemTypeManagementTable: true,
        SourceItemTypeFormDialog: true,
      },
    },
  })
}

describe('SourceItemTypeManagementView', () => {
  it('gates the create button on write:source_item_types and renders the table', () => {
    const withoutPermission = mountView([])
    const disabledButton = withoutPermission
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('icon') === 'mdi mdi-plus')!
    expect(disabledButton.attributes('disabled')).toBeDefined()
    withoutPermission.unmount()

    const withPermission = mountView([Permission.WRITE_SOURCE_ITEM_TYPES])
    const enabledButton = withPermission
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('icon') === 'mdi mdi-plus')!
    expect(enabledButton.attributes('disabled')).toBeUndefined()
    expect(
      withPermission.findComponent({ name: 'SourceItemTypeManagementTable' }).exists(),
    ).toBe(true)
    withPermission.unmount()
  })

  it('opens the create form dialog when the create button is clicked', async () => {
    const wrapper = mountView([Permission.WRITE_SOURCE_ITEM_TYPES])
    const button = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('icon') === 'mdi mdi-plus')!

    await button.trigger('click')

    expect(wrapper.findComponent({ name: 'SourceItemTypeFormDialog' }).props('visible')).toBe(
      true,
    )
    wrapper.unmount()
  })
})
