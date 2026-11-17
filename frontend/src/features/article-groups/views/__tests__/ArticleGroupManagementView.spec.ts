import { describe, it, expect } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { userWithPermissions } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { Permission } from '@/core/auth/permissions'

import ArticleGroupManagementView from '../ArticleGroupManagementView.vue'
import { useArticleGroupsStore } from '../../stores/articleGroupsStore'

function mountView(permissions: string[] = []) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)

  return mountWithApp(ArticleGroupManagementView, {
    pinia,
    global: {
      stubs: {
        ArticleGroupManagementTable: true,
        ArticleGroupFormDialog: true,
      },
    },
  })
}

describe('ArticleGroupManagementView', () => {
  it('renders the management table', () => {
    const wrapper = mountView()

    expect(wrapper.findComponent({ name: 'PageLayout' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'ArticleGroupManagementTable' }).exists()).toBe(true)

    wrapper.unmount()
  })

  it('gates the create button on write:article_groups', () => {
    const withoutPermission = mountView([])
    const disabledButton = withoutPermission
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('icon') === 'mdi mdi-plus')!
    expect(disabledButton.attributes('disabled')).toBeDefined()
    withoutPermission.unmount()

    const withPermission = mountView([Permission.WRITE_ARTICLE_GROUPS])
    const enabledButton = withPermission
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('icon') === 'mdi mdi-plus')!
    expect(enabledButton.attributes('disabled')).toBeUndefined()
    withPermission.unmount()
  })

  it('opens the create form dialog when the create button is clicked', async () => {
    const wrapper = mountView([Permission.WRITE_ARTICLE_GROUPS])
    const button = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('icon') === 'mdi mdi-plus')!

    await button.trigger('click')

    expect(wrapper.findComponent({ name: 'ArticleGroupFormDialog' }).props('visible')).toBe(true)

    wrapper.unmount()
  })

  it('wires the sort-by menu to the store, and binds the search field to store.search', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = userWithPermissions([Permission.WRITE_ARTICLE_GROUPS])

    const wrapper = mountWithApp(ArticleGroupManagementView, {
      pinia,
      global: {
        stubs: { ArticleGroupManagementTable: true, ArticleGroupFormDialog: true },
      },
    })

    const viewsBar = wrapper.findComponent({ name: 'ViewsBar' })
    expect(viewsBar.props('sortByItems')).toHaveLength(4)

    await viewsBar.vm.$emit('update:search', 'fasteners')

    expect(useArticleGroupsStore().search).toBe('fasteners')

    wrapper.unmount()
  })
})
