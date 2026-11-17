import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { userWithPermissions } from '@/test-utils/factories'
import { Permission } from '@/core/auth/permissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useArticleGroupsStore } from '../../stores/articleGroupsStore'

import type { ArticleGroupResponse } from '../../types/articleGroupResponse'

function makeArticleGroup(overrides: Partial<ArticleGroupResponse> = {}): ArticleGroupResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-01-01',
    changed: '2026-01-01T00:00:00Z',
    changed_by_id: null,
    changed_by: null,
    archived: false,
    name: { enGB: 'Sheet Metal' },
    label_color: '#ffffff',
    label_font_color: '#000000',
    description: { enGB: 'Sheet metal parts' },
    creator_id: 1,
    creator: null,
    ...overrides,
  }
}

function page(items: ArticleGroupResponse[], total = items.length) {
  return { data: { items, total, limit: 25, skip: 0 } }
}

const getMock = vi.fn<(url: string, config?: { params?: unknown }) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: { params?: unknown }) => getMock(url, config),
  },
}))

import ArticleGroupManagementTable from '../ArticleGroupManagementTable.vue'

describe('ArticleGroupManagementTable', () => {
  beforeEach(() => {
    getMock.mockReset()
  })

  it('mounts, loads article groups via the paginated fetch, and renders columns', async () => {
    getMock.mockResolvedValue(page([makeArticleGroup()]))

    const wrapper = mountWithApp(ArticleGroupManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Sheet Metal')
    expect(getMock).toHaveBeenCalledWith('/article-groups/', { params: { skip: 0, limit: 25 } })
  })

  it('is a lazy DataTable whose totalRecords comes from the server total', async () => {
    getMock.mockResolvedValue(page([makeArticleGroup()], 120))

    const wrapper = mountWithApp(ArticleGroupManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const table = wrapper.findComponent({ name: 'DataTable' })
    expect(table.props('lazy')).toBe(true)
    expect(table.props('totalRecords')).toBe(120)
  })

  it('requests the next page with the correct skip on @page', async () => {
    getMock.mockResolvedValue(page([makeArticleGroup()], 60))

    const wrapper = mountWithApp(ArticleGroupManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    getMock.mockClear()
    getMock.mockResolvedValue(
      page([makeArticleGroup({ id: 2, name: { enGB: 'Second Page Group' } })], 60),
    )

    const next = wrapper.find('[aria-label="Next Page"]')
    await next.trigger('click')
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/article-groups/', { params: { skip: 25, limit: 25 } })
  })

  // selectionMode="single" makes every row keyboard-reachable and gives
  // Enter the same effect as a click; both OpenVue events must still drive
  // the table's one existing @row-click behaviour (opening the detail
  // dialog) without double-firing it.
  it('makes the first row keyboard-focusable', async () => {
    getMock.mockResolvedValue(page([makeArticleGroup()]))
    const wrapper = mountWithApp(ArticleGroupManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    expect(row.exists()).toBe(true)
    expect(row.attributes('tabindex')).toBe('0')
  })

  it('opens the detail dialog on @row-select the same way @row-click does', async () => {
    const group = makeArticleGroup()
    getMock.mockResolvedValue(page([group]))
    const wrapper = mountWithApp(ArticleGroupManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'ResourceDetailDialog' }).props('visible')).toBe(false)

    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('row-select', { data: group, index: 0, originalEvent: new Event('keydown') })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'ResourceDetailDialog' }).props('visible')).toBe(true)
  })

  // Note: unlike OrdersTable's row-click (a toggle, where a double invoke is
  // directly observable, see OrdersTable.spec.ts for that empirical proof),
  // this table's handler just sets `visible = true`,
  // which is idempotent and so cannot itself distinguish one call from two.
  // The guard's suppression logic is exhaustively unit-tested in isolation
  // at useRowOpenGuard.spec.ts; a real click exercising it here (without
  // throwing/warning) is still a useful smoke check.
  //
  // It also checks that not binding v-model:selection is
  // essential: if bound, OpenVue tabindex computation returns -1
  // permanently, breaking keyboard access. selection is left unbound to
  // preserve keyboard reach.
  it('handles a real click - which fires both row-click and row-select - without error, and stays keyboard-reachable', async () => {
    const group = makeArticleGroup()
    getMock.mockResolvedValue(page([group]))
    const wrapper = mountWithApp(ArticleGroupManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    await row.trigger('click')
    await flushPromises()

    expect(wrapper.findComponent({ name: 'ResourceDetailDialog' }).props('visible')).toBe(true)
    expect(wrapper.find('tr[data-p-selectable-row="true"]').attributes('tabindex')).toBe('0')
  })

  it('stays keyboard-reachable (first row tabindex 0) after opening a row via Enter', async () => {
    const group = makeArticleGroup()
    getMock.mockResolvedValue(page([group]))
    const wrapper = mountWithApp(ArticleGroupManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    expect(row.attributes('tabindex')).toBe('0')

    await row.trigger('keydown', { code: 'Enter' })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'ResourceDetailDialog' }).props('visible')).toBe(true)
    expect(wrapper.find('tr[data-p-selectable-row="true"]').attributes('tabindex')).toBe('0')
  })

  // Under `lazy` OpenVue only emits @sort and fetches nothing itself, so the
  // table must wire the event or a header click would only toggle the icon.
  it('fetches with order_by/order_dir and resets to page 1 on a header sort click', async () => {
    getMock.mockResolvedValue(page([makeArticleGroup()], 60))
    const wrapper = mountWithApp(ArticleGroupManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    // Move off page 1 first, so the sort click's reset is observable.
    getMock.mockClear()
    getMock.mockResolvedValue(page([makeArticleGroup()], 60))
    await wrapper.find('[aria-label="Next Page"]').trigger('click')
    await flushPromises()

    getMock.mockClear()
    getMock.mockResolvedValue(page([makeArticleGroup()], 60))
    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('sort', { sortField: 'name', sortOrder: 1 })
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/article-groups/', {
      params: { skip: 0, limit: 25, order_by: 'name', order_dir: 'asc' },
    })
  })

  it('shows the Archived tag for an archived row', async () => {
    getMock.mockResolvedValue(page([makeArticleGroup({ archived: true })]))
    const wrapper = mountWithApp(ArticleGroupManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Archived')
  })

  it('shows a Restore row action for an archived row and an Archive row action for a live one', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useArticleGroupsStore().showActions = true

    getMock.mockResolvedValue(
      page([makeArticleGroup({ id: 1, archived: false }), makeArticleGroup({ id: 2, archived: true })]),
    )
    const wrapper = mountWithApp(ArticleGroupManagementTable, {
      pinia,
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const buttons = wrapper.findAllComponents({ name: 'Button' })
    expect(buttons.some((b) => b.attributes('aria-label') === 'Archive')).toBe(true)
    expect(buttons.some((b) => b.attributes('aria-label') === 'Restore')).toBe(true)
  })

  it('does not mark the description column sortable (not in the backend allow-list)', async () => {
    getMock.mockResolvedValue(page([makeArticleGroup()]))
    const wrapper = mountWithApp(ArticleGroupManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const column = wrapper
      .findAllComponents({ name: 'Column' })
      .find((c) => c.props('field') === 'description')
    expect(column?.props('sortable')).toBeFalsy()
  })

  it('drags a row onto a new place through the handle in the first column', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = userWithPermissions([Permission.WRITE_ARTICLE_GROUPS])
    const store = useArticleGroupsStore()
    const place = vi.spyOn(store, 'place').mockResolvedValue()

    getMock.mockResolvedValue(
      page([makeArticleGroup({ id: 1 }), makeArticleGroup({ id: 2 }), makeArticleGroup({ id: 3 })]),
    )
    const wrapper = mountWithApp(ArticleGroupManagementTable, {
      pinia,
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    expect(wrapper.findAll('[data-testid="row-drag-handle"]')).toHaveLength(3)
    const firstColumn = wrapper.findAllComponents({ name: 'Column' })[0]!
    expect(firstColumn.props('rowReorder')).toBe(true)

    wrapper.findComponent({ name: 'DataTable' }).vm.$emit('row-reorder', {
      originalEvent: new Event('drop'),
      dragIndex: 0,
      dropIndex: 2,
      value: [],
    })
    expect(place).toHaveBeenCalledWith(1, { after_id: 3 }, expect.any(Array))

    wrapper.findComponent({ name: 'DataTable' }).vm.$emit('row-reorder', {
      originalEvent: new Event('drop'),
      dragIndex: 2,
      dropIndex: 0,
      value: [],
    })
    expect(place).toHaveBeenLastCalledWith(3, { before_id: 1 }, expect.any(Array))
  })

  it('shows no drag handle without the write right or while a sort hides the order', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = userWithPermissions([])
    getMock.mockResolvedValue(page([makeArticleGroup({ id: 1 }), makeArticleGroup({ id: 2 })]))
    const wrapper = mountWithApp(ArticleGroupManagementTable, {
      pinia,
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()
    expect(wrapper.findAll('[data-testid="row-drag-handle"]')).toHaveLength(0)

    useCurrentUserStore().user = userWithPermissions([Permission.WRITE_ARTICLE_GROUPS])
    useArticleGroupsStore().setSort('name', 'asc')
    await flushPromises()
    expect(wrapper.findAll('[data-testid="row-drag-handle"]')).toHaveLength(0)
  })
})
