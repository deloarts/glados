import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Select from 'openvue/select'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeTestRouter } from '@/test-utils/factories'
import { makeListRow } from './meetingFixtures'
import type { MeetingListRowResponse, MeetingTagSuggestionsResponse } from '../types/meetingResponse'
import type { MeetingListParams } from '../types/meetingRequest'

const getMeetings = vi.fn<(params: MeetingListParams) => Promise<MeetingListRowResponse[]>>()
const getMeetingTagSuggestions = vi.fn<() => Promise<MeetingTagSuggestionsResponse>>()
vi.mock('../api/meetingsApi', () => ({
  getMeetings: (params: MeetingListParams) => getMeetings(params),
  getMeetingTagSuggestions: () => getMeetingTagSuggestions(),
  getMeeting: vi.fn<() => Promise<unknown>>(),
  deleteMeeting: vi.fn<() => Promise<void>>(),
}))

vi.mock('@/core/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: () => true }),
}))

import MeetingNotesTable from '../components/MeetingNotesTable.vue'
import { useMeetingNotesViewStore } from '../stores/meetingNotesViewStore'

const ROWS: MeetingListRowResponse[] = [
  makeListRow({
    id: 21,
    meeting_number: 'MTG-26-0021',
    starts_at: '2026-11-06T08:00:00Z',
    sent: true,
    printed: true,
    open_todo_count: 3,
    overdue_todo_count: 1,
    tags: ['Milestone', 'Factory acceptance'],
    scopes: [
      { scope: 'Vacuum gripper', icon: 'mechanics', internal: false },
      { scope: 'Fence, north door', icon: 'commercial', internal: true },
    ],
  }),
  makeListRow({
    id: 15,
    meeting_number: 'MTG-26-0015',
    name: 'Site Survey Fence',
    starts_at: '2026-10-21T08:00:00Z',
    valid: false,
    scopes: [],
    notes: '',
  }),
  makeListRow({
    id: 19,
    meeting_number: 'MTG-26-0019',
    name: 'Product Roadmap 2027',
    starts_at: '2026-11-03T09:00:00Z',
    owner: { kind: 'product', id: 31, number: 'PR-0031', product_id: null },
  }),
]

async function mountTable(ownerKind: 'project' | 'product' = 'project') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = makeTestRouter()
  await router.push('/')
  await router.isReady()
  const wrapper = mountWithApp(MeetingNotesTable, {
    pinia,
    props: { ownerKind, ownerId: ownerKind === 'project' ? 142 : 31 },
    global: { plugins: [router] },
  })
  await flushPromises()
  return { wrapper, router }
}

beforeEach(() => {
  getMeetings.mockResolvedValue(structuredClone(ROWS))
  getMeetingTagSuggestions.mockResolvedValue({
    suggestions: [
      { name: 'Milestone', count: 4 },
      { name: 'Factory acceptance', count: 1 },
    ],
  })
})

describe('MeetingNotesTable', () => {
  it('lists the meetings latest first with their status, scopes and open todos', async () => {
    const { wrapper } = await mountTable()

    expect(getMeetings).toHaveBeenCalledWith({ project_id: 142, include_projects: false, include_invalid: false })
    const rows = wrapper.findAll('tbody tr')
    expect(rows.map((row) => row.text())).toEqual([
      expect.stringContaining('MTG-26-0021'),
      expect.stringContaining('MTG-26-0019'),
      expect.stringContaining('MTG-26-0015'),
    ])
    expect(rows[0]?.text()).toContain('Valid')
    expect(rows[2]?.text()).toContain('Invalid')
    expect(rows[0]?.find('[data-testid="meeting-sent-icon"]').exists()).toBe(true)
    expect(rows[0]?.find('[data-testid="meeting-printed-icon"]').exists()).toBe(true)
    expect(rows[1]?.find('[data-testid="meeting-sent-icon"]').exists()).toBe(false)
    expect(rows[0]?.find('[data-testid="meeting-open-todos"]').text()).toContain('3')
    expect(rows[0]?.find('[data-testid="meeting-overdue-todos"]').text()).toBe('1 overdue')
    const chips = rows[0]?.findAll('[data-testid="meeting-scope-chip"]') ?? []
    expect(chips.map((chip) => chip.text())).toEqual(['Vacuum gripper', 'Fence, north door'])
    expect(chips[1]?.classes()).toContain('internal')
    expect(rows[2]?.text()).toContain('No notes yet')
  })

  it('opens the meeting of a clicked row', async () => {
    const { wrapper, router } = await mountTable()

    await wrapper.findAll('tbody tr')[0]?.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/workspace/projects/142/meeting-notes/21')
  })

  it('shows no Project column on a project', async () => {
    const { wrapper } = await mountTable()

    expect(wrapper.find('thead').text()).not.toContain('Project')
  })

  it('includes the projects of a product, with a Project column after Name once the Views menu turns it on', async () => {
    const { wrapper } = await mountTable('product')

    expect(getMeetings).toHaveBeenCalledWith({ product_id: 31, include_projects: true, include_invalid: false })
    expect(wrapper.find('thead').text()).not.toContain('Project')
    useMeetingNotesViewStore().showProjectColumn = true
    await flushPromises()
    const headers = wrapper.findAll('thead th').map((th) => th.text())
    expect(headers.indexOf('Project')).toBe(headers.indexOf('Name') + 1)
    const productRow = wrapper.findAll('tbody tr').find((row) => row.text().includes('MTG-26-0019'))
    expect(productRow?.text()).toContain('Product')
  })

  it('reads the list again with invalid meetings and without projects', async () => {
    await mountTable('product')
    const view = useMeetingNotesViewStore()

    view.showInvalid = true
    view.hideProjects = true
    await flushPromises()

    expect(getMeetings).toHaveBeenLastCalledWith({ product_id: 31, include_projects: false, include_invalid: true })
  })

  it('groups the meetings of a product by project, the product first', async () => {
    const { wrapper } = await mountTable('product')
    const view = useMeetingNotesViewStore()

    view.groupByProject = true
    await flushPromises()

    const text = wrapper.find('tbody').text()
    expect(text.indexOf('Product PR-0031')).toBeGreaterThanOrEqual(0)
    expect(text.indexOf('Product PR-0031')).toBeLessThan(text.indexOf('Project 26-0142'))
  })

  it('sorts by name when asked', async () => {
    const { wrapper } = await mountTable()
    const view = useMeetingNotesViewStore()

    view.setSort('nameAsc')
    await flushPromises()

    expect(wrapper.findAll('tbody tr')[0]?.text()).toContain('Design Review Gripper')
    expect(wrapper.findAll('tbody tr')[2]?.text()).toContain('Site Survey Fence')
  })

  it('shows the tags of each meeting in the Tags column', async () => {
    const { wrapper } = await mountTable()

    expect(wrapper.find('thead').text()).toContain('Tags')
    const rows = wrapper.findAll('tbody tr')
    const tags = rows[0]?.find('[data-testid="meeting-tags"]')
    expect(tags?.text()).toContain('Milestone')
    expect(tags?.text()).toContain('Factory acceptance')
    expect(rows[1]?.find('[data-testid="meeting-tags"]').exists()).toBe(false)
  })

  it('narrows the loaded list by a column filter without reading again, and Clear brings it back', async () => {
    const { wrapper } = await mountTable()
    const view = useMeetingNotesViewStore()
    const calls = getMeetings.mock.calls.length

    await wrapper.get('[data-testid="meeting-name-filter"]').setValue('survey')
    await flushPromises()

    expect(wrapper.findAll('tbody tr').map((row) => row.text())).toEqual([expect.stringContaining('MTG-26-0015')])
    expect(view.hasActiveFilters).toBe(true)
    expect(getMeetings.mock.calls.length).toBe(calls)

    view.clearAll()
    await flushPromises()

    expect(wrapper.findAll('tbody tr')).toHaveLength(3)
  })

  it('filters the list by a tag in use and clears the filter with the views', async () => {
    const { wrapper } = await mountTable()
    const view = useMeetingNotesViewStore()
    const filter = wrapper.findAllComponents(Select).find((select) => select.attributes('data-testid') === 'meeting-tag-filter')

    expect(filter?.props('options')).toEqual(['Milestone', 'Factory acceptance'])
    filter?.vm.$emit('update:modelValue', 'Milestone')
    await flushPromises()

    expect(view.tagFilter).toBe('Milestone')
    expect(view.hasActiveFilters).toBe(true)
    expect(getMeetings).toHaveBeenLastCalledWith({
      project_id: 142,
      include_projects: false,
      include_invalid: false,
      tag: 'Milestone',
    })

    view.clearAll()
    await flushPromises()

    expect(getMeetings).toHaveBeenLastCalledWith({ project_id: 142, include_projects: false, include_invalid: false })
  })
})
