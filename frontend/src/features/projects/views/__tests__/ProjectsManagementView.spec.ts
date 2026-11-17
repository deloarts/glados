import { describe, it, expect } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { userWithPermissions } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { Permission } from '@/core/auth/permissions'

import ProjectsManagementView from '../ProjectsManagementView.vue'

// Smoke spec for the View tier assembled from ManagementCrudShell. The
// Table (and its context-menu/detail/delete wiring) already has its own
// thorough spec, so this only proves the shell is wired correctly: the
// create button's label/permission gate, and that clicking it opens the
// feature's own create dialog. Table and FormDialog are stubbed so this
// spec needs no API mocking.
function mountView(permissions: string[] = []) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)

  return mountWithApp(ProjectsManagementView, {
    pinia,
    global: {
      stubs: {
        ProjectManagementTable: true,
        ProjectFormDialog: true,
      },
    },
  })
}

describe('ProjectsManagementView', () => {
  it('gates the create button on write:projects and renders the table', () => {
    const withoutPermission = mountView([])
    const disabledButton = withoutPermission
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('icon') === 'mdi mdi-plus')!
    expect(disabledButton.attributes('disabled')).toBeDefined()
    withoutPermission.unmount()

    const withPermission = mountView([Permission.WRITE_PROJECTS])
    const enabledButton = withPermission
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('icon') === 'mdi mdi-plus')!
    expect(enabledButton.attributes('disabled')).toBeUndefined()
    expect(
      withPermission.findComponent({ name: 'ProjectManagementTable' }).exists(),
    ).toBe(true)
    withPermission.unmount()
  })

  it('opens the create form dialog when the create button is clicked', async () => {
    const wrapper = mountView([Permission.WRITE_PROJECTS])
    const button = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('icon') === 'mdi mdi-plus')!

    await button.trigger('click')

    expect(wrapper.findComponent({ name: 'ProjectFormDialog' }).props('visible')).toBe(
      true,
    )
    wrapper.unmount()
  })
})
