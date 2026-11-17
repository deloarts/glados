import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'


const pushMock = vi.fn<(to: string) => void>()

// Partial mock: MadeItemDetailDialog's import chain reaches the real
// router module, which needs createRouter/createWebHistory to still exist.
vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRouter: () => ({ push: pushMock }),
  useRoute: () => ({ params: {} }),
}))

// The date cells load the user list for the actor's card; the generic API
// mock below would answer it with a bare array, so it gets an empty page.
vi.mock('@/core/api/users/getUserDirectory', () => ({
  getUserDirectory: async () => ({ items: [], total: 0, limit: 0, skip: 0 }),
}))

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: [] }),
  },
}))

import QaTaskTable from '../QaTaskTable.vue'
import { useQaTasksStore } from '../../stores/qaTasksStore'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { useHostStore } from '@/core/host/stores/hostStore'
import type { QaTaskResponse } from '../../types/qaTaskResponse'

function makeTask(overrides: Partial<QaTaskResponse> = {}): QaTaskResponse {
  return {
    id: 113,
    public_id: '11111111-1111-1111-1111-111111111111',
    production_order_number: 'FN-26-00024',
    status: 'queued',
    priority: 'normal',
    quantity: 6,
    quantity_completed: 0,
    planned_start: null,
    planned_end: null,
    actual_start: null,
    actual_end: null,
    finished_by: null,
    can_start: true,
    conflicts: [],
    inspection_method_id: 1,
    inspection_method_name: { enGB: 'Visual Inspection' },
    requires_evidence: false,
    has_evidence: false,
    evidence_files: [],
    lot_position_id: 160,
    lot_position_sequence: 3,
    lot_position_count: 3,
    lot_id: 78,
    lot_number: 'LN-26-00023',
    lot_status: 'in_progress',
    made_item_id: 16,
    made_item_part_number: 'TN-26-00006',
    made_item_article_name: 'Shaft',
    made_item_revision: '0',
    made_item_material: '1.3505',
    project_id: 3,
    project_number: 'P26003',
    project_customer: 'ROOFCO',
    ...overrides,
  }
}

function mountTable(
  tasks: QaTaskResponse[],
  storageEnabled = true,
  page: { first?: number; rows?: number; total?: number } = {},
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useQaTasksStore()
  store.tasks = tasks
  // The paginator reads the whole-worklist total, not the page length.
  store.total = page.total ?? tasks.length
  // The thumbnail, Documents and Evidence columns only render with file
  // storage on, which the host store reports.
  useHostStore().storageEnabled = storageEnabled
  return mountWithApp(QaTaskTable, {
    pinia,
    // The page window is owned by the view (useServerTable) and passed down.
    props: { first: page.first ?? 0, rows: page.rows ?? 25 },
  })
}

describe('QaTaskTable', () => {
  beforeEach(() => {
    pushMock.mockClear()
  })

  it('renders a row per task with the part and method', async () => {
    const wrapper = mountTable([makeTask()])
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('Shaft')
    expect(text).toContain('TN-26-00006')
    expect(text).toContain('Visual Inspection')
    expect(text).toContain('LN-26-00023')
  })

  // Same shape as the lots table's item cell: part number (with revision)
  // leads in bold, article name is the secondary line under it.
  it('leads the part cell with the part number and revision, article name beneath', async () => {
    const wrapper = mountTable([makeTask()])
    await flushPromises()
    const name = wrapper.find('.item-name')
    const code = wrapper.find('.item-code')
    expect(name.exists()).toBe(true)
    expect(name.text()).toBe('TN-26-00006:0')
    expect(code.text()).toBe('Shaft')
  })

  it('falls back to a warning when the part has no part number', async () => {
    const wrapper = mountTable([makeTask({ made_item_part_number: '' })])
    await flushPromises()
    expect(wrapper.find('.item-name').exists()).toBe(false)
    expect(wrapper.find('.item-name-warning').exists()).toBe(true)
  })

  // The evidence badge is the thing that tells a QA engineer a task will
  // refuse to submit, so it must show before the task is opened.
  it('flags a task whose method needs evidence that is not on file', async () => {
    const wrapper = mountTable([makeTask({ requires_evidence: true, has_evidence: false })])
    await flushPromises()
    expect(wrapper.text()).toContain('Evidence missing')
  })

  it('shows evidence as satisfied once a report is on file', async () => {
    const wrapper = mountTable([makeTask({ requires_evidence: true, has_evidence: true })])
    await flushPromises()
    expect(wrapper.text()).toContain('Evidence on file')
    expect(wrapper.text()).not.toContain('Evidence missing')
  })

  it('says nothing about evidence for a method that does not need it', async () => {
    const wrapper = mountTable([makeTask({ requires_evidence: false })])
    await flushPromises()
    expect(wrapper.text()).not.toContain('Evidence missing')
    expect(wrapper.text()).not.toContain('Evidence on file')
  })

  it('marks a startable task Ready and a blocked one Waiting', async () => {
    const ready = mountTable([makeTask({ can_start: true })])
    await flushPromises()
    expect(ready.text()).toContain('Ready')

    const blocked = mountTable([makeTask({ can_start: false })])
    await flushPromises()
    expect(blocked.text()).toContain('Waiting')
  })

  it('numbers the rows', async () => {
    const wrapper = mountTable([makeTask({ id: 1 }), makeTask({ id: 2 })])
    await flushPromises()
    const firstCells = wrapper.findAll('tbody tr').map((r) => r.findAll('td')[0])
    expect(firstCells[0]!.text()).toBe('1')
    expect(firstCells[1]!.text()).toBe('2')
  })

  it('leaves Finished empty while the task is still open', async () => {
    const wrapper = mountTable([makeTask({ actual_end: null, finished_by: null })])
    await flushPromises()
    expect(wrapper.findComponent({ name: 'UserAvatarPreview' }).exists()).toBe(false)
  })

  it('shows who finished the inspection once it is recorded', async () => {
    const wrapper = mountTable([
      makeTask({
        actual_end: '2026-08-14T16:30:00Z',
        finished_by: {
          id: 7,
          public_id: 'u',
          username: 'anna',
          full_name: 'Anna Mock',
          email: 'a@e.com',
          has_avatar: false,
        } as QaTaskResponse['finished_by'],
      }),
    ])
    await flushPromises()
    expect(wrapper.findComponent({ name: 'UserAvatarPreview' }).exists()).toBe(true)
  })

  it('shows one clickable icon per attached evidence file', async () => {
    const wrapper = mountTable([
      makeTask({
        requires_evidence: true,
        has_evidence: true,
        evidence_files: [
          { id: 1, file_name: 'report.pdf', mime_type: 'application/pdf', category: 'measurement_report', url: 'blob:x' },
          { id: 2, file_name: 'photo.jpg', mime_type: 'image/jpeg', category: 'measurement_report', url: 'blob:y' },
        ],
      }),
    ])
    await flushPromises()
    const icons = wrapper.findAll('.qa-evidence-cell .evidence-icon')
    expect(icons).toHaveLength(2)
    // The icon distinguishes a scanned report from a shop-floor photo.
    expect(icons[0]!.classes()).toContain('mdi-file-pdf-box')
    expect(icons[1]!.classes()).toContain('mdi-file-image')
  })

  it('renders an empty evidence cell when nothing is attached', async () => {
    const wrapper = mountTable([makeTask({ evidence_files: [] })])
    await flushPromises()
    expect(wrapper.findAll('.qa-evidence-cell .evidence-icon')).toHaveLength(0)
  })

  it('navigates to the task detail page when Inspect is clicked', async () => {
    const wrapper = mountTable([makeTask({ id: 113 })])
    await flushPromises()
    const inspect = wrapper.findAll('button').find((b) => b.text().includes('Inspect'))
    expect(inspect).toBeDefined()
    await inspect!.trigger('click')
    expect(pushMock).toHaveBeenCalledWith('/production/qa/113')
  })

  // selectionMode="single" makes the row keyboard-reachable
  // and gives Enter the same effect as a click, via the shared
  // useRowOpenGuard recipe proven on OrdersTable/ArticleGroupManagementTable.
  it('makes the first row keyboard-focusable', async () => {
    const wrapper = mountTable([makeTask({ id: 113 })])
    await flushPromises()

    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    expect(row.exists()).toBe(true)
    expect(row.attributes('tabindex')).toBe('0')
  })

  it('navigates to the task detail page on @row-select the same way @row-click does', async () => {
    const task = makeTask({ id: 113 })
    const wrapper = mountTable([task])
    await flushPromises()

    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('row-select', { data: task, index: 0, originalEvent: new Event('keydown') })
    await flushPromises()

    expect(pushMock).toHaveBeenCalledWith('/production/qa/113')
  })

  it('renders an empty state that explains the hidden future tasks', async () => {
    const wrapper = mountTable([])
    await flushPromises()
    expect(wrapper.text()).toContain('Nothing waiting for inspection')
    expect(wrapper.text()).toContain('Show Future Tasks')
  })

  // ── Paging ──────────────────────────────────────────────────────────

  it('renders a paginator driven by the whole-worklist total', async () => {
    const wrapper = mountTable([makeTask()], true, { rows: 25, total: 120 })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'Paginator' }).exists()).toBe(true)
    // 120 rows at 25 a page: the last page button proves it counted pages
    // from the server total rather than from the one row it was handed.
    const pageButtons = wrapper.findAll('[aria-label^="Page "]')
    expect(pageButtons.map((b) => b.text())).toContain('5')
  })

  it('continues row numbers across pages instead of restarting at 1', async () => {
    const wrapper = mountTable([makeTask()], true, { first: 25, rows: 25, total: 120 })
    await flushPromises()
    const firstCell = wrapper.find('tbody tr td')
    expect(firstCell.text()).toBe('26')
  })

  it('reports page changes up to the view rather than paging itself', async () => {
    const wrapper = mountTable([makeTask(), makeTask({ id: 114 })], true, { rows: 25, total: 60 })
    await flushPromises()
    const next = wrapper.find('[aria-label="Next Page"]')
    await next.trigger('click')
    await flushPromises()
    // lazy: the table emits and the view refetches; it must not slice the
    // rows it already has.
    expect(wrapper.emitted('page')).toBeTruthy()
  })
})
