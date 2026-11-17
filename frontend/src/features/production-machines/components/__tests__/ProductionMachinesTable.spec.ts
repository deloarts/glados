import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { makeTestRouter, userWithPermissions } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { Permission } from '@/core/auth/permissions'
import { machineStatusTooltip } from '../../utils/machineStatus'
import { useProductionMachinesStore } from '../../stores/productionMachinesStore'
import type { ProductionMachineResponse } from '../../types/productionMachinesResponse'

// The created cells load the user list for the creator's card; it stays
// empty here so the request does not reach the API mock below.
vi.mock('@/core/api/users/getUserDirectory', () => ({
  getUserDirectory: async () => ({ items: [], total: 0, limit: 0, skip: 0 }),
}))

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: {
        items: [
          {
            id: 1,
            archived: false,
            created: '2026-01-01',
            changed: null,
            internal_name: 'CNC-01',
            vendor: 'Contoso',
            model: 'VF-2',
            fabrication_method_ids: [2],
            fabrication_methods: [
              {
                id: 2,
                created: '2026-01-01',
                changed: null,
                archived: false,
                name: 'Milling',
                description: '',
                label_color: '#6366f1',
                label_font_color: '#ffffff',
                creator_id: 1,
                creator: null,
                parent_id: 1,
                has_children: false,
                children: [],
              },
            ],
            max_part_dimension: '400x400x300mm',
            note: 'Primary mill',
            creator_id: 1,
            creator_full_name: 'Creator',
            changes: [],
          },
        ],
        total: 1,
        limit: 25,
        skip: 0,
      },
    }),
  },
}))

import ProductionMachinesTable from '../ProductionMachinesTable.vue'

// ProductionMachinesTable calls useRouter() (its row-action/context-menu
// "view machine" entry navigates to the machine detail page), so a router
// plugin is required for the
// component to mount without a "injection not found" warning tripping the
// no-console-noise assertion below.
function machineFixture(
  overrides: Partial<ProductionMachineResponse> & { id: number; internal_name: string },
): ProductionMachineResponse {
  return {
    archived: false,
    created: '2026-01-01',
    changed: null,
    changed_by_id: null,
    changed_by_full_name: '',
    vendor: 'Contoso',
    model: 'VF-2',
    fabrication_method_ids: [],
    fabrication_methods: [],
    max_part_dimension: null,
    note: null,
    is_qa_machine: false,
    creator_id: 1,
    creator_full_name: 'Creator',
    changes: [],
    public_id: '11111111-1111-1111-1111-111111111111',
    status: 'idle',
    active_orders: [],
    live_order_count: 0,
    open_downtime: null,
    ...overrides,
  }
}

describe('ProductionMachinesTable', () => {
  it('mounts, loads machines, and renders columns without errors', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountWithApp(ProductionMachinesTable, {
      global: {
        plugins: [makeTestRouter(), ConfirmationService],
      },
    })

    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])
    expect(wrapper.text()).toContain('CNC-01')
    expect(wrapper.text()).toContain('Milling')

    wrapper.unmount()
  })

  it('shows an "Add downtime" entry in the row context menu', async () => {
    const wrapper = mountWithApp(ProductionMachinesTable, {
      global: {
        plugins: [makeTestRouter(), ConfirmationService],
      },
    })

    await flushPromises()
    await flushPromises()

    const row = wrapper.find('tbody tr')
    expect(row.exists()).toBe(true)
    await row.trigger('contextmenu')
    await flushPromises()

    expect(document.body.textContent).toContain('Add Downtime')

    wrapper.unmount()
  })

  it('renders a Down status tag when the machine has an open downtime', async () => {
    const { default: api } = await import('@/core/api')
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 2,
            archived: false,
            created: '2026-01-01',
            changed: null,
            internal_name: 'CNC-02',
            vendor: 'Contoso',
            model: 'VF-3',
            fabrication_method_ids: [],
            fabrication_methods: [],
            max_part_dimension: null,
            note: null,
            creator_id: 1,
            creator_full_name: 'Creator',
            changes: [],
            open_downtime: { id: 5, started_at: '2026-01-01T08:00:00Z', reason: 'breakdown' },
            status: 'down',
            active_orders: [],
            live_order_count: 0,
          },
        ],
        total: 1,
        limit: 25,
        skip: 0,
      },
    })

    const wrapper = mountWithApp(ProductionMachinesTable, {
      global: {
        plugins: [makeTestRouter(), ConfirmationService],
      },
    })

    await flushPromises()
    await flushPromises()

    expect(wrapper.text()).toContain('Down')

    wrapper.unmount()
  })

  it('renders a sequential row number for each machine', async () => {
    const { default: api } = await import('@/core/api')
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        items: [
          machineFixture({ id: 1, internal_name: 'ROW-1' }),
          machineFixture({ id: 2, internal_name: 'ROW-2' }),
          machineFixture({ id: 3, internal_name: 'ROW-3' }),
        ],
        total: 3,
        limit: 25,
        skip: 0,
      },
    })

    const wrapper = mountWithApp(ProductionMachinesTable, {
      global: {
        plugins: [makeTestRouter(), ConfirmationService],
      },
    })

    await flushPromises()
    await flushPromises()

    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(3)
    // The "#" column is the first cell since showActions defaults to false.
    expect(rows.map((row) => row.findAll('td')[0]?.text())).toEqual(['1', '2', '3'])

    wrapper.unmount()
  })

  it('renders the correct status tag severity and label per machine', async () => {
    const { default: api } = await import('@/core/api')
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        items: [
          machineFixture({ id: 1, internal_name: 'IDLE-1', status: 'idle' }),
          machineFixture({
            id: 2,
            internal_name: 'RUNNING-1',
            status: 'running',
            active_orders: [{ id: 100, production_order_number: 'PO-100', status: 'in_progress' }],
            live_order_count: 0,
          }),
          machineFixture({
            id: 3,
            internal_name: 'PAUSED-1',
            status: 'paused',
            active_orders: [{ id: 101, production_order_number: 'PO-101', status: 'paused' }],
            live_order_count: 0,
          }),
          machineFixture({
            id: 4,
            internal_name: 'DOWN-1',
            status: 'down',
            open_downtime: { id: 5, started_at: '2026-01-01T08:00:00Z', reason: 'breakdown' },
          }),
        ],
        total: 4,
        limit: 25,
        skip: 0,
      },
    })

    const wrapper = mountWithApp(ProductionMachinesTable, {
      global: {
        plugins: [makeTestRouter(), ConfirmationService],
      },
    })

    await flushPromises()
    await flushPromises()

    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(4)
    // The status column's Tag is the first Tag component in each row;
    // the "#" and internal-name cells render no Tag of their own.
    const severities = rows.map((row) => row.findComponent({ name: 'Tag' }).props('severity'))
    expect(severities).toEqual(['secondary', 'success', 'warn', 'danger'])

    expect(rows[0]?.text()).toContain('Idle')
    expect(rows[1]?.text()).toContain('Running')
    expect(rows[2]?.text()).toContain('Paused')
    expect(rows[3]?.text()).toContain('Down')

    wrapper.unmount()
  })

  it('builds the status tooltip text for each status', () => {
    const t = i18n.global.t.bind(i18n.global) as (
      key: string,
      params?: Record<string, unknown>,
    ) => string

    const down = machineFixture({
      id: 1,
      internal_name: 'DOWN-1',
      status: 'down',
      open_downtime: { id: 1, started_at: '2026-01-01T08:00:00Z', reason: 'breakdown' },
    })
    expect(machineStatusTooltip(down, t)).toContain('Breakdown')

    const running = machineFixture({
      id: 2,
      internal_name: 'RUNNING-1',
      status: 'running',
      active_orders: [{ id: 10, production_order_number: 'PO-42', status: 'in_progress' }],
      live_order_count: 0,
    })
    expect(machineStatusTooltip(running, t)).toBe('PO-42')

    const paused = machineFixture({
      id: 3,
      internal_name: 'PAUSED-1',
      status: 'paused',
      active_orders: [{ id: 11, production_order_number: 'PO-43', status: 'paused' }],
      live_order_count: 0,
    })
    expect(machineStatusTooltip(paused, t)).toBe('PO-43')

    const idle = machineFixture({ id: 4, internal_name: 'IDLE-1', status: 'idle' })
    expect(machineStatusTooltip(idle, t)).toBe(t('productionMachines.status.noOrderTooltip'))
  })

  it('sends a capability filter immediately and loads the method list only when needed', async () => {
    const apiModule = await import('@/core/api')
    const getMock = apiModule.default.get as ReturnType<typeof vi.fn>
    getMock.mockClear()

    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useProductionMachinesStore()

    const wrapper = mountWithApp(ProductionMachinesTable, {
      pinia,
      global: {
        plugins: [makeTestRouter(), ConfirmationService],
      },
    })
    await flushPromises()

    const urls = getMock.mock.calls.map((call) => call[0])
    expect(urls).toEqual(['/production-machines/'])

    getMock.mockClear()
    store.filters = {
      ...store.filters,
      fabrication_method_id: { value: 2, matchMode: 'equals' },
      creator_id: { value: 1, matchMode: 'equals' },
    }
    await flushPromises()

    expect(getMock).toHaveBeenCalledTimes(1)
    expect(getMock).toHaveBeenLastCalledWith('/production-machines/', {
      params: expect.objectContaining({ fabrication_method_id: 2, creator_id: 1, skip: 0 }),
    })
    expect(store.hasActiveFilters).toBe(true)

    getMock.mockClear()
    store.clearAll()
    await flushPromises()
    const lastCall = getMock.mock.lastCall
    expect(lastCall).toBeDefined()
    const lastParams = (lastCall![1] as { params: Record<string, unknown> }).params
    expect(lastParams).not.toHaveProperty('fabrication_method_id')
    expect(lastParams).not.toHaveProperty('creator_id')

    wrapper.unmount()
  })

  it('disables Archive on a machine that still has live production orders', async () => {
    const { default: api } = await import('@/core/api')
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        items: [
          machineFixture({ id: 1, internal_name: 'BUSY', live_order_count: 2 }),
          machineFixture({ id: 2, internal_name: 'IDLE' }),
        ],
        total: 2,
        limit: 25,
        skip: 0,
      },
    })
    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = userWithPermissions([Permission.WRITE_MACHINES])
    useProductionMachinesStore().showActions = true

    const wrapper = mountWithApp(ProductionMachinesTable, {
      pinia,
      global: { plugins: [makeTestRouter(), ConfirmationService] },
    })
    await flushPromises()
    await flushPromises()

    const archive = wrapper.findAll(`button[aria-label="${i18n.global.t('common.archive')}"]`)
    expect(archive).toHaveLength(2)
    expect(archive[0]!.attributes('disabled')).toBeDefined()
    expect(archive[1]!.attributes('disabled')).toBeUndefined()

    wrapper.unmount()
  })

  it('gives the disabled Archive menu entry of a busy machine the reason the button shows', async () => {
    const { default: api } = await import('@/core/api')
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        items: [machineFixture({ id: 1, internal_name: 'BUSY', live_order_count: 2 })],
        total: 1,
        limit: 25,
        skip: 0,
      },
    })
    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = userWithPermissions([Permission.WRITE_MACHINES])

    const wrapper = mountWithApp(ProductionMachinesTable, {
      pinia,
      attachTo: document.body,
      global: { plugins: [makeTestRouter(), ConfirmationService] },
    })
    await flushPromises()
    await flushPromises()

    await wrapper.find('tbody tr').trigger('contextmenu')
    await flushPromises()

    const reason = i18n.global.t('productionMachines.archiveBlocked', 2)
    const archive = Array.from(document.body.querySelectorAll('[role="menuitem"] a')).find(
      (link) => link.textContent?.includes(i18n.global.t('common.archive')),
    )
    expect(archive?.getAttribute('title')).toBe(reason)

    wrapper.unmount()
  })

  it('drags a machine to a new place, but shows no handle while the table is grouped', async () => {
    const { default: api } = await import('@/core/api')
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        items: [
          machineFixture({ id: 1, internal_name: 'M1' }),
          machineFixture({ id: 2, internal_name: 'M2' }),
        ],
        total: 2,
        limit: 25,
        skip: 0,
      },
    })
    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = userWithPermissions([Permission.WRITE_MACHINES])
    const store = useProductionMachinesStore()
    const place = vi.spyOn(store, 'place').mockResolvedValue()

    const wrapper = mountWithApp(ProductionMachinesTable, {
      pinia,
      global: { plugins: [makeTestRouter(), ConfirmationService] },
    })
    await flushPromises()
    await flushPromises()

    expect(wrapper.findAll('[data-testid="row-drag-handle"]')).toHaveLength(2)
    wrapper.findComponent({ name: 'DataTable' }).vm.$emit('row-reorder', {
      originalEvent: new Event('drop'),
      dragIndex: 0,
      dropIndex: 1,
      value: [],
    })
    expect(place).toHaveBeenCalledWith(1, { after_id: 2 }, expect.any(Array))

    store.groupBy = 'capability'
    await flushPromises()
    expect(wrapper.findAll('[data-testid="row-drag-handle"]')).toHaveLength(0)

    wrapper.unmount()
  })
})
