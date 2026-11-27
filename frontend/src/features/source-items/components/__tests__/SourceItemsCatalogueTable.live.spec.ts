import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { LIVE_COALESCE_MS } from '@/core/realtime/constants'
import { LiveResource } from '@/core/realtime/resources'
import type { LiveSignal } from '@/core/realtime/types'

const liveHandlers = vi.hoisted(() => new Map<string, (signal: LiveSignal) => void>())
// What the list endpoint answers with, changed by a test to stand for an
// edit made elsewhere.
const listState = vi.hoisted(() => ({ material: 'Steel' }))

vi.mock('@/core/realtime/liveStore', () => ({
  useLiveStore: () => ({
    reconnectCount: 0,
    on: (resource: string, handler: (signal: LiveSignal) => void) => {
      liveHandlers.set(resource, handler)
      return () => liveHandlers.delete(resource)
    },
  }),
}))

vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRouter: () => ({ push: vi.fn<(to: string) => void>() }),
}))

vi.mock('@/core/api', () => {
  const creator = {
    id: 1,
    username: 'creator',
    full_name: 'Creator',
    email: 'creator@example.com',
    has_avatar: false,
  }
  return {
    default: {
      get: vi.fn<(url: string) => Promise<unknown>>().mockImplementation((url: string) => {
        if (url.includes('/thumbnail')) {
          return Promise.reject({ isAxiosError: true, response: { status: 404 } })
        }
        return Promise.resolve({
          data: {
            items: [
              {
                id: 1,
                public_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
                status: 'active',
                archived: false,
                created: '2026-01-01',
                changed: null,
                type_id: 1,
                type_name: 'Rod',
                dimension: '10mm',
                material: listState.material,
                mass: 100,
                note: null,
                order_code_1: null,
                order_code_2: null,
                successor_item_id: null,
                creator_id: 1,
                creator,
                approver_id: null,
                manufacturer_id: null,
                manufacturer_name: '',
              },
            ],
            total: 1,
            limit: 25,
            skip: 0,
          },
        })
      }),
    },
  }
})

import api from '@/core/api'
import SourceItemsCatalogueTable from '../SourceItemsCatalogueTable.vue'
import { useSourceItemsStore } from '../../stores/sourceItemsStore'

type GetCall = [string, { params?: Record<string, unknown> }?]

function listCalls(): GetCall[] {
  return (vi.mocked(api.get).mock.calls as GetCall[]).filter(([url]) => url === '/source-items')
}

function signal(id: number, action: LiveSignal['action']): LiveSignal {
  return { resource: LiveResource.SOURCE_ITEMS, id, action, actor_id: null }
}

async function mountTable() {
  mountWithApp(SourceItemsCatalogueTable, { global: { plugins: [ConfirmationService] } })
  await flushPromises()
  vi.mocked(api.get).mockClear()
}

async function waitForCoalescedFlush(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, LIVE_COALESCE_MS + 10))
  await flushPromises()
}

describe('SourceItemsCatalogueTable live sync', () => {
  beforeEach(() => {
    liveHandlers.clear()
    listState.material = 'Steel'
  })

  it('refetches a changed row by id with the current filters and replaces it', async () => {
    await mountTable()
    listState.material = 'Renamed elsewhere'

    liveHandlers.get(LiveResource.SOURCE_ITEMS)!(signal(1, 'updated'))
    await waitForCoalescedFlush()

    const [[, config]] = listCalls() as [GetCall]
    expect(config?.params).toMatchObject({ ids: [1] })
    expect(config?.params).not.toHaveProperty('skip')
    expect(useSourceItemsStore().items[0]!.material).toBe('Renamed elsewhere')
  })

  it('ignores a change to a row that is not on the page', async () => {
    await mountTable()

    liveHandlers.get(LiveResource.SOURCE_ITEMS)!(signal(99, 'updated'))
    await waitForCoalescedFlush()

    expect(listCalls()).toEqual([])
  })

  it('reloads the page when an item is created elsewhere', async () => {
    await mountTable()

    liveHandlers.get(LiveResource.SOURCE_ITEMS)!(signal(2, 'created'))
    await flushPromises()

    const [[, config]] = listCalls() as [GetCall]
    expect(config?.params).toMatchObject({ skip: 0 })
    expect(config?.params).not.toHaveProperty('ids')
  })
})
