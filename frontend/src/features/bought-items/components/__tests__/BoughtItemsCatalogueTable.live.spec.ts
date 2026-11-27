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
const listState = vi.hoisted(() => ({ articleName: 'Article' }))

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
                part_number: 'PN-1',
                status: 'active',
                archived: false,
                created: '2026-01-01',
                changed: '2026-02-01',
                order_code_1: 'OC1',
                order_code_2: null,
                gtin: null,
                ean: null,
                tariff_number: null,
                article_name: listState.articleName,
                article_groups: [],
                data_source: 'WEB',
                mass: 100,
                note: null,
                weblink: null,
                successor_item_id: null,
                creator_id: 1,
                creator,
                manufacturer_id: 1,
                manufacturer_name: 'Manufacturer',
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
import BoughtItemsCatalogueTable from '../BoughtItemsCatalogueTable.vue'
import { useBoughtItemsStore } from '../../stores/boughtItemsStore'

type GetCall = [string, { params?: Record<string, unknown> }?]

function listCalls(): GetCall[] {
  return (vi.mocked(api.get).mock.calls as GetCall[]).filter(([url]) => url === '/bought-items/')
}

function signal(id: number, action: LiveSignal['action']): LiveSignal {
  return { resource: LiveResource.BOUGHT_ITEMS, id, action, actor_id: null }
}

async function mountTable() {
  mountWithApp(BoughtItemsCatalogueTable, { global: { plugins: [ConfirmationService] } })
  await flushPromises()
  vi.mocked(api.get).mockClear()
}

async function waitForCoalescedFlush(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, LIVE_COALESCE_MS + 10))
  await flushPromises()
}

describe('BoughtItemsCatalogueTable live sync', () => {
  beforeEach(() => {
    liveHandlers.clear()
    listState.articleName = 'Article'
  })

  it('refetches a changed row by id with the current filters and replaces it', async () => {
    await mountTable()
    listState.articleName = 'Renamed elsewhere'

    liveHandlers.get(LiveResource.BOUGHT_ITEMS)!(signal(1, 'updated'))
    await waitForCoalescedFlush()

    const [[, config]] = listCalls() as [GetCall]
    expect(config?.params).toMatchObject({ ids: [1] })
    expect(config?.params).not.toHaveProperty('skip')
    expect(useBoughtItemsStore().items[0]!.article_name).toBe('Renamed elsewhere')
  })

  it('ignores a change to a row that is not on the page', async () => {
    await mountTable()

    liveHandlers.get(LiveResource.BOUGHT_ITEMS)!(signal(99, 'updated'))
    await waitForCoalescedFlush()

    expect(listCalls()).toEqual([])
  })

  it('reloads the page when an item is created elsewhere', async () => {
    await mountTable()

    liveHandlers.get(LiveResource.BOUGHT_ITEMS)!(signal(2, 'created'))
    await flushPromises()

    const [[, config]] = listCalls() as [GetCall]
    expect(config?.params).toMatchObject({ skip: 0 })
    expect(config?.params).not.toHaveProperty('ids')
  })
})
