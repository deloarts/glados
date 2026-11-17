import { describe, it, expect, vi } from 'vitest'

import { demandContextMenu, type DemandContextMenuConfig } from '../demandContextMenu'

import type { MenuItem } from 'openvue/menuitem'

interface Demand {
  id: number
  public_id: string
  actions: string[]
}

const LIVE: Demand = { id: 1, public_id: 'a', actions: ['cancel', 'fulfil', 'allocate'] }
const ENDED: Demand = { id: 2, public_id: 'b', actions: [] }

function config(
  targets: Demand[],
  overrides: Partial<DemandContextMenuConfig<Demand>> = {},
): DemandContextMenuConfig<Demand> {
  return {
    t: (key: string) => key,
    keyPrefix: 'x',
    targets,
    canEdit: true,
    canSetStatus: true,
    canWriteBuckets: true,
    canWriteAllocations: true,
    showCopyPlaceholder: false,
    bucketItems: () => [],
    openDetail: vi.fn<(demand: Demand) => void>(),
    setStatus: vi.fn<(demand: Demand, status: string) => void>(),
    fulfilTargets: vi.fn<(targets: Demand[]) => void>(),
    requestBulkCancel: vi.fn<(targets: Demand[]) => void>(),
    panel: {
      label: 'Add to Order',
      icon: 'mdi mdi-cart-arrow-right',
      disabled: false,
      action: 'allocate',
      open: vi.fn<() => void>(),
      addDemand: vi.fn<(demand: Demand) => void>(),
    },
    quotePanel: {
      label: 'Add to Quote Request',
      icon: 'mdi mdi-scale-balance',
      disabled: false,
      action: 'allocate',
      open: vi.fn<() => void>(),
      addDemand: vi.fn<(demand: Demand) => void>(),
    },
    openStockPanel: vi.fn<() => void>(),
    singleEntries: () => [],
    copyToClipboard: vi.fn<(text: string) => void>(),
    ...overrides,
  }
}

function labels(items: MenuItem[]): (string | undefined)[] {
  return items.map((item) => (item.separator ? '---' : (item.label as string | undefined)))
}

describe('demandContextMenu', () => {
  it('leaves the panel entries out for a demand without their action, and no double separator', () => {
    const items = demandContextMenu(config([ENDED]))

    expect(labels(items)).not.toContain('Add to Order')
    expect(labels(items)).not.toContain('Add to Quote Request')
    const separatorsInARow = items.some((item, i) => item.separator && items[i - 1]?.separator)
    expect(separatorsInARow).toBe(false)
  })

  it('keeps the panel entries for a live demand, disabled with their reason without the rights', () => {
    const base = config([LIVE])
    const items = demandContextMenu({
      ...base,
      panel: { ...base.panel, disabled: true, disabledReason: 'Needs write:orders.' },
    })

    expect(items.find((item) => item.label === 'Add to Order')).toMatchObject({
      disabled: true,
      title: 'Needs write:orders.',
    })
    expect(items.find((item) => item.label === 'Add to Quote Request')).toMatchObject({
      disabled: false,
    })
  })

  it('keeps the panel entries for several targets, whatever their actions', () => {
    const items = demandContextMenu(config([ENDED, { ...ENDED, id: 3 }]))

    expect(labels(items)).toContain('Add to Order')
    expect(labels(items)).toContain('Add to Quote Request')
  })

  it("gives one demand's disabled Canceled status entry its reason, and Set Status the permission", () => {
    const blocked = { ...LIVE, actions: ['fulfil', 'allocate'] }
    const items = demandContextMenu(
      config([blocked], {
        canSetStatus: false,
        setStatusDisabledReason: 'Needs manage:demand_items.',
        cancelDisabledReason: () => 'The lot has started.',
      }),
    )

    const status = items.find((item) => item.label === 'x.contextMenu.setStatus')
    expect(status).toMatchObject({ disabled: true, title: 'Needs manage:demand_items.' })
    const cancel = ((status?.items ?? []) as MenuItem[]).find((item) => item.label === 'x.status.canceled')
    expect(cancel).toMatchObject({ disabled: true, title: 'The lot has started.' })
  })

  it('gives an enabled Canceled status entry no title', () => {
    const items = demandContextMenu(
      config([LIVE], { cancelDisabledReason: () => 'The lot has started.' }),
    )

    const status = items.find((item) => item.label === 'x.contextMenu.setStatus')
    const cancel = ((status?.items ?? []) as MenuItem[]).find((item) => item.label === 'x.status.canceled')
    expect(cancel?.disabled).toBe(false)
    expect(cancel?.title).toBeUndefined()
    expect(status?.title).toBeUndefined()
  })
})
