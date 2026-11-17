import { describe, it, expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { h } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import Column from 'openvue/column'

import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { mountWithApp } from '@/test-utils/mountWithApp'
import DemandsTableShell from '../DemandsTableShell.vue'
import type { DemandsTableShellLabels } from '../demandsTableShell'

interface Row {
  id: number
  name: string
  desired_delivery_date: string | null
  created: string
  creator: null
  _projectGroup?: string
}

function makeRow(overrides: Partial<Row> = {}): Row {
  return {
    id: 1,
    name: 'Bracket',
    desired_delivery_date: '2026-03-01',
    created: '2026-02-01T08:00:00Z',
    creator: null,
    ...overrides,
  }
}

const labels: DemandsTableShellLabels = {
  desiredDelivery: 'Desired',
  created: 'Created',
  dateFilterPlaceholder: 'Filter by',
  creatorPlaceholder: 'Any',
  bulkCancelHeader: 'Cancel demands',
  bulkCancelMessage: 'Cancel 2 demands?',
  bulkCancelAction: 'Cancel them',
}

function shellOptions(props: Record<string, unknown> = {}, slots: Record<string, unknown> = {}) {
  return {
    props: {
      items: [makeRow()],
      total: 1,
      first: 0,
      rows: 25,
      filters: {},
      groupBy: null,
      groupRowsBy: undefined,
      groupIcons: { project: 'mdi mdi-folder-outline' },
      showSelectionColumn: false,
      showActions: false,
      actionsWidth: '8rem',
      contextMenuItems: [],
      labels,
      selection: [],
      contextMenuSelection: null,
      bulkCancelVisible: false,
      desiredRange: null,
      creatorId: null,
      ...props,
    },
    slots: {
      columns: () => h(Column, { field: 'name', header: 'Name' }),
      ...slots,
    },
    attachTo: document.body,
  }
}

function mountShell(props: Record<string, unknown> = {}, slots: Record<string, unknown> = {}) {
  return mountWithApp(DemandsTableShell, shellOptions(props, slots) as never)
}

function headerTexts(wrapper: ReturnType<typeof mountShell>): string[] {
  return wrapper.findAll('thead tr:first-child th').map((th) => th.text())
}

describe('DemandsTableShell', () => {
  it('renders the kind columns between the row number and the shared closing columns', async () => {
    const wrapper = mountShell()
    await flushPromises()

    expect(headerTexts(wrapper)).toEqual(['#', 'Name', 'Desired', 'Created', ''])
    expect(wrapper.find('tbody tr').text()).toContain('Bracket')
    expect(wrapper.find('tbody tr').text()).toContain('2026-03-01')
    wrapper.unmount()
  })

  it('numbers rows from the current page offset', async () => {
    const wrapper = mountShell({ first: 50 })
    await flushPromises()

    expect(wrapper.find('tbody tr td').text()).toBe('51')
    wrapper.unmount()
  })

  it('renders the row actions slot with the row only while actions are shown', async () => {
    const slots = {
      'row-actions': ({ data }: { data: Row }) => h('button', { class: 'kind-action' }, `open ${data.id}`),
    }
    const hidden = mountShell({}, slots)
    await flushPromises()
    expect(hidden.find('.kind-action').exists()).toBe(false)
    hidden.unmount()

    const shown = mountShell({ showActions: true }, slots)
    await flushPromises()
    expect(shown.find('.row-actions .kind-action').text()).toBe('open 1')
    shown.unmount()
  })

  it('always shows the selection column to a user who can change demands', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = { id: 1, permissions: ['write:demand_items'], is_systemuser: false } as never
    const wrapper = mountWithApp(DemandsTableShell, { ...shellOptions(), pinia } as never)
    await flushPromises()
    // One box per row plus the select all box in the header.
    expect(wrapper.findAll('input[type="checkbox"]')).toHaveLength(2)
    expect(wrapper.find('thead input[type="checkbox"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('shows the selection column to a user without the right only when asked to', async () => {
    const hidden = mountShell()
    await flushPromises()
    expect(hidden.find('input[type="checkbox"]').exists()).toBe(false)
    hidden.unmount()

    const shown = mountShell({ showSelectionColumn: true })
    await flushPromises()
    expect(shown.find('input[type="checkbox"]').exists()).toBe(true)
    shown.unmount()
  })

  it('filters the created column by creator only while its range is unbound', async () => {
    const withoutRange = mountShell()
    await flushPromises()
    expect(withoutRange.findComponent({ name: 'UserDateFilter' }).props('userOnly')).toBe(true)
    withoutRange.unmount()

    const withRange = mountShell({ createdRange: null })
    await flushPromises()
    expect(withRange.findComponent({ name: 'UserDateFilter' }).props('userOnly')).toBe(false)
    withRange.unmount()
  })

  it('writes the creator and the created range back from the created filter', async () => {
    const wrapper = mountShell({ createdRange: null })
    await flushPromises()

    const filter = wrapper.findComponent({ name: 'UserDateFilter' })
    const range = [new Date(2026, 1, 1), null]
    filter.vm.$emit('update:userId', 4)
    filter.vm.$emit('update:range', range)

    expect(wrapper.emitted('update:creatorId')).toEqual([[4]])
    expect(wrapper.emitted('update:createdRange')).toEqual([[range]])
    wrapper.unmount()
  })

  it('writes the desired range back and clears it from the filter', async () => {
    const wrapper = mountShell()
    await flushPromises()

    const filter = wrapper.findComponent({ name: 'DemandDateRangeFilter' })
    const range = [new Date(2026, 2, 1), new Date(2026, 2, 31)]
    filter.vm.$emit('update:modelValue', range)
    filter.vm.$emit('clear-click')

    expect(wrapper.emitted('update:desiredRange')).toEqual([[range], [null]])
    wrapper.unmount()
  })

  it('forwards row clicks with the clicked row', async () => {
    const row = makeRow({ id: 7 })
    const wrapper = mountShell({ items: [row] })
    await flushPromises()

    await wrapper.find('tbody tr').trigger('click')

    const events = wrapper.emitted('row-click') as [{ data: Row }][]
    expect(events).toHaveLength(1)
    expect(events[0]![0].data).toEqual(row)
    wrapper.unmount()
  })

  it('labels group headers from the grouping field and uses the kind icon', async () => {
    const wrapper = mountShell({
      items: [makeRow({ _projectGroup: 'P-001' })],
      groupBy: 'project',
      groupRowsBy: '_projectGroup',
    })
    await flushPromises()

    expect(wrapper.find('.group-header-label').text()).toBe('P-001')
    expect(wrapper.find('.group-header i').classes()).toContain('mdi-folder-outline')
    wrapper.unmount()
  })

  it('clears the context menu selection when the menu hides', async () => {
    const wrapper = mountShell({ contextMenuItems: [{ label: 'Edit' }], contextMenuSelection: makeRow() })
    await flushPromises()

    wrapper.findComponent({ name: 'ContextMenu' }).vm.$emit('hide')

    expect(wrapper.emitted('update:contextMenuSelection')).toEqual([[null]])
    wrapper.unmount()
  })

  it('shows the bulk cancel labels and reports a confirm', async () => {
    const wrapper = mountShell({ bulkCancelVisible: true })
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'ConfirmActionDialog' })
    expect(dialog.props('header')).toBe('Cancel demands')
    expect(dialog.props('message')).toBe('Cancel 2 demands?')
    expect(dialog.props('confirmLabel')).toBe('Cancel them')
    dialog.vm.$emit('confirm')

    expect(wrapper.emitted('confirm-bulk-cancel')).toHaveLength(1)
    wrapper.unmount()
  })
})
