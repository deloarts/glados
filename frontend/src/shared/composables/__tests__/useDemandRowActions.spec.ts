import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { useDemandRowActions, type DemandRowActionsDeps } from '../useDemandRowActions'

type TestStatus = 'open' | 'fulfilled' | 'canceled'

interface TestDemand {
  id: number
  status: TestStatus
  actions?: string[]
}

interface Harness {
  deps: DemandRowActionsDeps<TestStatus, TestDemand>
  openDetail: ReturnType<typeof vi.fn<(demand: TestDemand) => void>>
  fetchItems: ReturnType<typeof vi.fn<() => void>>
  updateStatus: ReturnType<typeof vi.fn<(id: number, status: TestStatus) => Promise<unknown>>>
  setBucket: ReturnType<typeof vi.fn<(id: number, bucketId: number | null) => Promise<unknown>>>
  setSelection: (demands: TestDemand[]) => void
  getSelection: () => TestDemand[]
  setPanelOpen: (value: boolean) => void
}

function makeHarness(
  updateStatus: ReturnType<
    typeof vi.fn<(id: number, status: TestStatus) => Promise<unknown>>
  > = vi.fn<(id: number, status: TestStatus) => Promise<unknown>>(),
): Harness {
  let selection: TestDemand[] = []
  let panelOpen = false
  const openDetail = vi.fn<(demand: TestDemand) => void>()
  const fetchItems = vi.fn<() => void>()
  const setBucket = vi.fn<(id: number, bucketId: number | null) => Promise<unknown>>()

  const deps: DemandRowActionsDeps<TestStatus, TestDemand> = {
    getSelection: () => selection,
    setSelection: (demands) => {
      selection = demands
    },
    hasPanelOpen: () => panelOpen,
    openDetail,
    guardRowOpen: (_id, open) => open(),
    fetchItems,
    updateStatus,
    setBucket,
    canceledStatus: 'canceled',
  }

  return {
    deps,
    openDetail,
    fetchItems,
    updateStatus,
    setBucket,
    setSelection: deps.setSelection,
    getSelection: deps.getSelection,
    setPanelOpen: (value: boolean) => {
      panelOpen = value
    },
  }
}

function clickEvent(data: TestDemand, modifiers: Partial<MouseEvent> = {}) {
  return {
    data,
    index: 0,
    originalEvent: { ctrlKey: false, metaKey: false, shiftKey: false, ...modifiers } as MouseEvent,
  }
}

function selectEvent(data: TestDemand, type: string, modifiers: Partial<MouseEvent> = {}) {
  return {
    data,
    index: 0,
    type,
    originalEvent: { ctrlKey: false, metaKey: false, shiftKey: false, ...modifiers } as MouseEvent,
  }
}

describe('useDemandRowActions', () => {
  describe('onRowClick / onRowSelect', () => {
    it('opens detail on a plain click while no panel is open', () => {
      const { deps, openDetail } = makeHarness()
      const rowActions = useDemandRowActions(deps)
      const demand: TestDemand = { id: 1, status: 'open' }

      rowActions.onRowClick(clickEvent(demand))

      expect(openDetail).toHaveBeenCalledWith(demand)
    })

    it('does not open detail on a click while a panel is open', () => {
      const { deps, openDetail, setPanelOpen } = makeHarness()
      setPanelOpen(true)
      const rowActions = useDemandRowActions(deps)
      const demand: TestDemand = { id: 1, status: 'open' }

      rowActions.onRowClick(clickEvent(demand))

      expect(openDetail).not.toHaveBeenCalled()
    })

    it('does not open detail on a modified click', () => {
      const { deps, openDetail } = makeHarness()
      const rowActions = useDemandRowActions(deps)
      const demand: TestDemand = { id: 1, status: 'open' }

      rowActions.onRowClick(clickEvent(demand, { ctrlKey: true }))

      expect(openDetail).not.toHaveBeenCalled()
    })

    it('onRowSelect ignores non-row selection types (checkbox toggles)', () => {
      const { deps, openDetail } = makeHarness()
      const rowActions = useDemandRowActions(deps)
      const demand: TestDemand = { id: 1, status: 'open' }

      rowActions.onRowSelect(selectEvent(demand, 'checkbox'))

      expect(openDetail).not.toHaveBeenCalled()
    })

    it('a plain row select clears the selection and opens detail', () => {
      const { deps, openDetail, setSelection, getSelection } = makeHarness()
      setSelection([{ id: 9, status: 'open' }])
      const rowActions = useDemandRowActions(deps)
      const demand: TestDemand = { id: 1, status: 'open' }

      rowActions.onRowSelect(selectEvent(demand, 'row'))

      expect(getSelection()).toEqual([])
      expect(openDetail).toHaveBeenCalledWith(demand)
    })

    it('while a panel is open, a plain row select restores the selection from before the click', () => {
      const { deps, openDetail, setSelection, getSelection, setPanelOpen } = makeHarness()
      const existing: TestDemand[] = [{ id: 9, status: 'open' }]
      setSelection(existing)
      setPanelOpen(true)
      const rowActions = useDemandRowActions(deps)
      const demand: TestDemand = { id: 1, status: 'open' }

      // onRowClick fires before onRowSelect for the same interaction and
      // snapshots the selection OpenVue is about to replace.
      rowActions.onRowClick(clickEvent(demand))
      rowActions.onRowSelect(selectEvent(demand, 'row'))

      expect(getSelection()).toEqual(existing)
      expect(openDetail).not.toHaveBeenCalled()
    })
  })

  describe('onTableClickCapture', () => {
    it('replays a modified click on the selectable row when the target is a nested element', () => {
      const { deps } = makeHarness()
      const rowActions = useDemandRowActions(deps)

      const table = document.createElement('table')
      const tbody = document.createElement('tbody')
      const row = document.createElement('tr')
      row.setAttribute('data-p-selectable-row', 'true')
      const cell = document.createElement('td')
      row.appendChild(cell)
      tbody.appendChild(row)
      table.appendChild(tbody)
      document.body.appendChild(table)

      const dispatchSpy = vi.spyOn(row, 'dispatchEvent')
      const event = new MouseEvent('click', { ctrlKey: true, bubbles: true, cancelable: true })
      Object.defineProperty(event, 'target', { value: cell })
      const preventSpy = vi.spyOn(event, 'preventDefault')

      rowActions.onTableClickCapture(event)

      expect(preventSpy).toHaveBeenCalled()
      expect(dispatchSpy).toHaveBeenCalled()

      table.remove()
    })

    it('does nothing for an unmodified click', () => {
      const { deps } = makeHarness()
      const rowActions = useDemandRowActions(deps)
      const event = new MouseEvent('click')
      const preventSpy = vi.spyOn(event, 'preventDefault')

      rowActions.onTableClickCapture(event)

      expect(preventSpy).not.toHaveBeenCalled()
    })
  })

  describe('contextMenuTargets', () => {
    it('is empty when no row was right-clicked', () => {
      const { deps } = makeHarness()
      const rowActions = useDemandRowActions(deps)

      expect(rowActions.contextMenuTargets.value).toEqual([])
    })

    it('is just the row when it is not part of the current selection', () => {
      const { deps } = makeHarness()
      const rowActions = useDemandRowActions(deps)
      const row: TestDemand = { id: 1, status: 'open' }

      rowActions.contextMenuItem.value = row

      expect(rowActions.contextMenuTargets.value).toEqual([row])
    })

    it('is the whole selection when the right-clicked row is part of it', () => {
      const { deps, setSelection } = makeHarness()
      const row: TestDemand = { id: 1, status: 'open' }
      const other: TestDemand = { id: 2, status: 'open' }
      setSelection([row, other])
      const rowActions = useDemandRowActions(deps)

      rowActions.contextMenuItem.value = row

      expect(rowActions.contextMenuTargets.value).toEqual([row, other])
    })
  })

  // A live demand offers both manual actions; a fulfilled or canceled one
  // offers neither (the demand intent table).
  function live(id: number): TestDemand {
    return { id, status: 'open', actions: ['cancel', 'fulfil'] }
  }

  function finished(id: number, status: TestStatus): TestDemand {
    return { id, status, actions: [] }
  }

  describe('setStatusForTargets', () => {
    it('only updates targets whose actions offer the change', async () => {
      const { deps, updateStatus, fetchItems } = makeHarness()
      const rowActions = useDemandRowActions(deps)
      const targets: TestDemand[] = [
        live(1),
        finished(2, 'fulfilled'),
      ]

      await rowActions.setStatusForTargets(targets, 'fulfilled')

      expect(updateStatus).toHaveBeenCalledTimes(1)
      expect(updateStatus).toHaveBeenCalledWith(1, 'fulfilled')
      expect(fetchItems).toHaveBeenCalled()
    })

    it('does nothing when no target offers the change', async () => {
      const { deps, updateStatus, fetchItems } = makeHarness()
      const rowActions = useDemandRowActions(deps)
      const targets: TestDemand[] = [finished(1, 'fulfilled')]

      await rowActions.setStatusForTargets(targets, 'fulfilled')

      expect(updateStatus).not.toHaveBeenCalled()
      expect(fetchItems).not.toHaveBeenCalled()
    })

    it('reports a failure count without throwing when an update rejects', async () => {
      const updateStatus = vi
        .fn<(id: number, status: TestStatus) => Promise<unknown>>()
        .mockRejectedValue(new Error('boom'))
      const { deps } = makeHarness(updateStatus)
      const rowActions = useDemandRowActions(deps)
      const onFailures = vi.fn<(failures: number, applicable: number) => void>()

      await rowActions.setStatusForTargets([live(1)], 'fulfilled', onFailures)

      expect(onFailures).toHaveBeenCalledWith(1, 1)
    })
  })

  describe('bulk cancel flow', () => {
    it('requestBulkCancel keeps only the targets that offer a cancel and opens the confirm dialog', () => {
      const { deps } = makeHarness()
      const rowActions = useDemandRowActions(deps)
      const targets: TestDemand[] = [
        live(1),
        finished(2, 'canceled'),
      ]

      rowActions.requestBulkCancel(targets)

      expect(rowActions.bulkCancelTargets.value).toEqual([targets[0]])
      expect(rowActions.showBulkCancel.value).toBe(true)
    })

    it('requestBulkCancel does not open the dialog when no target offers a cancel', () => {
      const { deps } = makeHarness()
      const rowActions = useDemandRowActions(deps)

      rowActions.requestBulkCancel([finished(1, 'canceled')])

      expect(rowActions.showBulkCancel.value).toBe(false)
    })

    it('confirmBulkCancel hides the dialog and cancels the staged targets', async () => {
      const { deps, updateStatus } = makeHarness()
      const rowActions = useDemandRowActions(deps)
      rowActions.requestBulkCancel([live(1)])

      rowActions.confirmBulkCancel()
      await flushPromises()

      expect(rowActions.showBulkCancel.value).toBe(false)
      expect(updateStatus).toHaveBeenCalledWith(1, 'canceled')
    })
  })

  describe('fulfil confirm', () => {
    it('requestFulfil keeps only the targets that offer a fulfil and opens the confirm dialog', () => {
      const { deps, updateStatus } = makeHarness()
      const rowActions = useDemandRowActions(deps)
      const targets: TestDemand[] = [live(1), finished(2, 'fulfilled')]

      rowActions.requestFulfil(targets)

      expect(rowActions.fulfilTargets.value).toEqual([targets[0]])
      expect(rowActions.showFulfil.value).toBe(true)
      expect(updateStatus).not.toHaveBeenCalled()
    })

    it('requestFulfil does not open the dialog when no target offers a fulfil', () => {
      const { deps } = makeHarness()
      const rowActions = useDemandRowActions(deps)

      rowActions.requestFulfil([finished(1, 'fulfilled')])

      expect(rowActions.showFulfil.value).toBe(false)
    })
  })

  describe('assignBucket', () => {
    it('sets the bucket on every target and refetches', async () => {
      const { deps, setBucket, fetchItems } = makeHarness()
      const rowActions = useDemandRowActions(deps)
      const targets: TestDemand[] = [
        { id: 1, status: 'open' },
        { id: 2, status: 'open' },
      ]

      await rowActions.assignBucket(targets, 5)

      expect(setBucket).toHaveBeenCalledWith(1, 5)
      expect(setBucket).toHaveBeenCalledWith(2, 5)
      expect(fetchItems).toHaveBeenCalled()
    })
  })
})
