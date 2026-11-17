import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { userWithPermissions } from '@/test-utils/factories'
import { Permission } from '@/core/auth/permissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { i18n } from '@/core/i18n'
import { TABLE_DEBOUNCE_MS } from '@/core/constants/table'
import { useMachinePoolsStore } from '../../stores/machinePoolsStore'

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
            public_id: '11111111-1111-1111-1111-111111111111',
            archived: false,
            created: '2026-01-01',
            changed: null,
            name: 'Milling pool',
            note: null,
            machine_ids: [],
            machines: [],
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

import MachinePoolsTable from '../MachinePoolsTable.vue'

function mountTable() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useMachinePoolsStore()
  const wrapper = mountWithApp(MachinePoolsTable, {
    pinia,
    global: {
      plugins: [ConfirmationService],
    },
  })
  return { store, wrapper }
}

describe('MachinePoolsTable row filters', () => {
  it('mounts with a filter row and fetches only the pools, not the machine options', async () => {
    const apiModule = await import('@/core/api')
    const getMock = apiModule.default.get as ReturnType<typeof vi.fn>
    getMock.mockClear()

    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const { wrapper } = mountTable()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(logs).toEqual([])
    expect(wrapper.text()).toContain('Milling pool')
    const nameLabel = i18n.global.t('common.filterBy', {
      column: i18n.global.t('productionMachinePools.columns.name'),
    })
    expect(wrapper.find(`input[aria-label="${nameLabel}"]`).exists()).toBe(true)
    expect(getMock.mock.calls.map((call) => call[0])).toEqual(['/production-machine-pools/'])

    wrapper.unmount()
  })

  it('debounces the name filter and sends the machine filter right away', async () => {
    const apiModule = await import('@/core/api')
    const getMock = apiModule.default.get as ReturnType<typeof vi.fn>

    const { store, wrapper } = mountTable()
    await flushPromises()
    getMock.mockClear()

    const nameLabel = i18n.global.t('common.filterBy', {
      column: i18n.global.t('productionMachinePools.columns.name'),
    })
    await wrapper.find(`input[aria-label="${nameLabel}"]`).setValue('mill')
    expect(getMock).not.toHaveBeenCalled()

    await new Promise((resolve) => setTimeout(resolve, TABLE_DEBOUNCE_MS + 50))
    await flushPromises()
    expect(getMock).toHaveBeenLastCalledWith('/production-machine-pools/', {
      params: expect.objectContaining({ name: 'mill', skip: 0 }),
    })

    getMock.mockClear()
    store.filters = { ...store.filters, machine_id: { value: 12, matchMode: 'equals' } }
    await flushPromises()
    expect(getMock).toHaveBeenCalledTimes(1)
    expect(getMock).toHaveBeenLastCalledWith('/production-machine-pools/', {
      params: expect.objectContaining({ name: 'mill', machine_id: 12 }),
    })
    expect(store.hasActiveFilters).toBe(true)

    store.clearAll()
    await flushPromises()
    expect(store.hasActiveFilters).toBe(false)
    const lastCall = getMock.mock.lastCall
    expect(lastCall).toBeDefined()
    const lastParams = (lastCall![1] as { params: Record<string, unknown> }).params
    expect(lastParams).not.toHaveProperty('machine_id')

    wrapper.unmount()
  })
})

describe('MachinePoolsTable drag reorder', () => {
  it('shows the drag handle to users who may edit machines and places the dropped row', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = userWithPermissions([Permission.WRITE_MACHINES])
    const store = useMachinePoolsStore()
    const place = vi.spyOn(store, 'place').mockResolvedValue()
    const wrapper = mountWithApp(MachinePoolsTable, {
      pinia,
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    expect(wrapper.findAll('[data-testid="row-drag-handle"]')).toHaveLength(1)
    store.tableItems = [
      { ...store.tableItems[0]!, id: 1 },
      { ...store.tableItems[0]!, id: 2 },
    ]
    wrapper.findComponent({ name: 'DataTable' }).vm.$emit('row-reorder', {
      originalEvent: new Event('drop'),
      dragIndex: 1,
      dropIndex: 0,
      value: [],
    })
    expect(place).toHaveBeenCalledWith(2, { before_id: 1 }, expect.any(Array))
  })

  it('shows no drag handle without the right to edit machines', async () => {
    const { wrapper } = mountTable()
    await flushPromises()
    expect(wrapper.findAll('[data-testid="row-drag-handle"]')).toHaveLength(0)
  })
})
