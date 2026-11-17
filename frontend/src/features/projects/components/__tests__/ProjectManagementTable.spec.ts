import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { Permission } from '@/core/auth/permissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { userWithPermissions } from '@/test-utils/factories'
import { useProjectsStore } from '../../stores/projectsStore'

import type { ProjectResponse } from '../../types/projectResponse'

const pushMock = vi.fn<(to: string) => void>()

// Partial mock: only useRouter's `push` needs to be observable here. The
// rest of vue-router (RouterLink et al, used elsewhere in the tree) must
// still be the real module.
vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRouter: () => ({ push: pushMock }),
}))

function makeProject(overrides: Partial<ProjectResponse> = {}): ProjectResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    project_number: 'PRJ-001',
    customer_id: null,
    customer: null,
    product_id: null,
    product: null,
    description: null,
    status: 'active',
    designated_user_id: 1,
    created: '2026-01-01',
    changed: null,
    changed_by_id: null,
    changed_by: null,
    creator_id: 1,
    creator: null,
    production_time_budget: null,
    required_delivery_date_made: null,
    required_delivery_date_bought: null,
    edit_version: 0,
    actions: [],
    live_work: null,
    ...overrides,
  }
}

function page(items: ProjectResponse[], total = items.length) {
  return { data: { items, total, limit: 25, skip: 0 } }
}

// Empty envelope for the other lists this table lazily prefetches on mount
// (usersStore/customersStore, used for its own picker cells/filters). They
// hit different URLs and aren't the concern of these tests.
function emptyPage() {
  return { data: { items: [], total: 0, limit: 25, skip: 0 } }
}

const getMock = vi.fn<(url: string, config?: { params?: unknown }) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: { params?: unknown }) => getMock(url, config),
  },
}))

import ProjectManagementTable from '../ProjectManagementTable.vue'

describe('ProjectManagementTable', () => {
  beforeEach(() => {
    getMock.mockReset()
    pushMock.mockClear()
  })

  it('mounts, loads projects via the paginated fetch, and renders columns', async () => {
    getMock.mockImplementation((url: string) =>
      Promise.resolve(url === '/projects/' ? page([makeProject()]) : emptyPage()),
    )

    const wrapper = mountWithApp(ProjectManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('PRJ-001')
    expect(getMock).toHaveBeenCalledWith('/projects/', { params: { skip: 0, limit: 25 } })
  })

  it('is a lazy DataTable whose totalRecords comes from the server total', async () => {
    getMock.mockImplementation((url: string) =>
      Promise.resolve(url === '/projects/' ? page([makeProject()], 120) : emptyPage()),
    )

    const wrapper = mountWithApp(ProjectManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const table = wrapper.findComponent({ name: 'DataTable' })
    expect(table.props('lazy')).toBe(true)
    expect(table.props('totalRecords')).toBe(120)
  })

  it('requests the next page with the correct skip on @page', async () => {
    getMock.mockImplementation((url: string) =>
      Promise.resolve(url === '/projects/' ? page([makeProject()], 60) : emptyPage()),
    )

    const wrapper = mountWithApp(ProjectManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    getMock.mockClear()
    getMock.mockImplementation((url: string) =>
      Promise.resolve(
        url === '/projects/'
          ? page([makeProject({ id: 2, project_number: 'PRJ-002' })], 60)
          : emptyPage(),
      ),
    )

    const next = wrapper.find('[aria-label="Next Page"]')
    await next.trigger('click')
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/projects/', { params: { skip: 25, limit: 25 } })
  })

  // selectionMode="single" makes every row keyboard-reachable and gives
  // Enter the same effect as a click, via the shared useRowOpenGuard recipe
  // proven on OrdersTable/ArticleGroupManagementTable.
  it('makes the first row keyboard-focusable', async () => {
    getMock.mockImplementation((url: string) =>
      Promise.resolve(url === '/projects/' ? page([makeProject()]) : emptyPage()),
    )

    const wrapper = mountWithApp(ProjectManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    expect(row.exists()).toBe(true)
    expect(row.attributes('tabindex')).toBe('0')
  })

  it('navigates to the project detail page on @row-select the same way @row-click does', async () => {
    const project = makeProject({ id: 7 })
    getMock.mockImplementation((url: string) =>
      Promise.resolve(url === '/projects/' ? page([project]) : emptyPage()),
    )

    const wrapper = mountWithApp(ProjectManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('row-select', { data: project, index: 0, originalEvent: new Event('keydown') })
    await flushPromises()

    expect(pushMock).toHaveBeenCalledWith('/workspace/projects/7')
  })

  // Under `lazy` OpenVue only emits @sort and fetches nothing itself, so the
  // table must wire the event or a header click would only toggle the icon.
  it('fetches with order_by/order_dir and resets to page 1 on a header sort click', async () => {
    getMock.mockImplementation((url: string) =>
      Promise.resolve(url === '/projects/' ? page([makeProject()], 60) : emptyPage()),
    )

    const wrapper = mountWithApp(ProjectManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    // Move off page 1 first, so the sort click's reset is observable.
    getMock.mockClear()
    getMock.mockImplementation((url: string) =>
      Promise.resolve(url === '/projects/' ? page([makeProject()], 60) : emptyPage()),
    )
    await wrapper.find('[aria-label="Next Page"]').trigger('click')
    await flushPromises()

    getMock.mockClear()
    getMock.mockImplementation((url: string) =>
      Promise.resolve(url === '/projects/' ? page([makeProject()], 60) : emptyPage()),
    )
    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('sort', { sortField: 'project_number', sortOrder: 1 })
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/projects/', {
      params: { skip: 0, limit: 25, order_by: 'project_number', order_dir: 'asc' },
    })
  })

  it('does not mark the customer column sortable (not in the backend allow-list)', async () => {
    getMock.mockImplementation((url: string) =>
      Promise.resolve(url === '/projects/' ? page([makeProject()]) : emptyPage()),
    )
    const wrapper = mountWithApp(ProjectManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const column = wrapper
      .findAllComponents({ name: 'Column' })
      .find((c) => c.props('field') === 'customer_id')
    expect(column?.props('sortable')).toBeFalsy()
  })

  describe('edit button tooltip', () => {
    const t = i18n.global.t

    async function editButton(permissions: string[], project: ProjectResponse) {
      getMock.mockImplementation((url: string) =>
        Promise.resolve(url === '/projects/' ? page([project]) : emptyPage()),
      )
      const pinia = createPinia()
      setActivePinia(pinia)
      useCurrentUserStore().user = userWithPermissions(permissions, { id: 1 })
      useProjectsStore().showActions = true
      const wrapper = mountWithApp(ProjectManagementTable, {
        pinia,
        global: { plugins: [ConfirmationService] },
      })
      await flushPromises()
      const button = wrapper.get(`button[aria-label="${t('resources.projects.editProject')}"]`)
      const span = button.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
      return { disabled: button.attributes('disabled') !== undefined, tooltip: span?.$_ptooltipValue }
    }

    it('names Write Projects when the user lacks it', async () => {
      expect(await editButton([], makeProject())).toEqual({
        disabled: true,
        tooltip: t('common.permissionMissing', {
          permission: t('settings.users.permissions.writeProjects'),
        }),
      })
    })

    it('says only the designated user edits when the user writes projects but is not designated', async () => {
      expect(
        await editButton([Permission.WRITE_PROJECTS], makeProject({ designated_user_id: 2 })),
      ).toEqual({ disabled: true, tooltip: t('resources.projects.detail.editDesignatedOnly') })
    })

    it('shows the plain label to the designated user', async () => {
      expect(await editButton([Permission.WRITE_PROJECTS], makeProject())).toEqual({
        disabled: false,
        tooltip: t('resources.projects.editProject'),
      })
    })
  })
})
