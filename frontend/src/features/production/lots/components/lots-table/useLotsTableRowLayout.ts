import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { FilterMatchMode } from '@openvue/core/api'

import { groupRowsByLabel } from '@/core/utils/tableRowGrouping'
import { useProductionLotsStore } from '../../../stores/productionLotsStore'
import { useProductionLotsFiltersStore } from '../../stores/productionLotsFiltersStore'
import { useProductionLotsEditStore } from '../../stores/productionLotsEditStore'
import { positionGroups } from '../../utils/lotPositionGroups'
import { stepColumnClass } from '../../utils/lotStepColumns'
import { LOT_PRIORITIES, LOT_STATUSES } from '../../../utils/lotStatus'

import type { DataTableFilterMeta } from 'openvue/datatable'
import type { FlatPositionRow } from '../../types/lotsTableFlatRow'
import type { LotStepGroup } from '../../utils/lotPositionGroups'
import type { LotSummaryResponse } from '../../../types/productionLotsResponse'

// Shapes the rows LotsTable renders across its Column, Widescreen and Simple
// modes, plus the visuals Column Mode needs because a lot spans several <tr>s.
export function useLotsTableRowLayout(isTableStripedEnabled: Ref<boolean>, showManageSource: Ref<boolean>) {
  const { t } = useI18n()
  const lotsStore = useProductionLotsStore()
  const filtersStore = useProductionLotsFiltersStore()
  const editStore = useProductionLotsEditStore()

  const statusOptions = computed(() =>
    LOT_STATUSES.map((s) => ({ label: t(`production.lots.status.${s}`), value: s })),
  )

  const priorityOptions = computed(() =>
    LOT_PRIORITIES.map((p) => ({ label: t(`production.lots.priority.${p}`), value: p })),
  )

  const visibleLots = computed(() =>
    lotsStore.items.filter((lot) => {
      if (filtersStore.hideCompleted && lot.status === 'completed') return false
      if (filtersStore.hideCanceled && lot.status === 'canceled') return false
      return true
    }),
  )

  const groupedLots = computed(() => {
    if (filtersStore.groupBy === 'status') {
      return groupRowsByLabel(visibleLots.value, '_statusGroup', (lot) =>
        t(`production.lots.status.${lot.status}`),
      )
    }
    if (filtersStore.groupBy === 'priority') {
      return groupRowsByLabel(visibleLots.value, '_priorityGroup', (lot) =>
        t(`production.lots.priority.${lot.priority}`),
      )
    }
    if (filtersStore.groupBy === 'project') {
      return groupRowsByLabel(visibleLots.value, '_projectGroup', (lot) => lot.project_number)
    }
    return visibleLots.value
  })

  const subheaderGroupRowsBy = computed(() => {
    if (filtersStore.groupBy === 'status') return '_statusGroup'
    if (filtersStore.groupBy === 'priority') return '_priorityGroup'
    if (filtersStore.groupBy === 'project') return '_projectGroup'
    return undefined
  })

  // Widescreen Mode gives each position its own column group.
  const maxPositionCount = computed(() =>
    visibleLots.value.reduce((max, lot) => Math.max(max, positionGroups(lot).length), 0),
  )

  const isColumnModeActive = computed(() => !filtersStore.widescreenMode && !filtersStore.simpleMode)

  const stepGroupCount = computed(() => (isColumnModeActive.value ? 1 : maxPositionCount.value))

  function stepGroupHeader(n: number): string {
    return isColumnModeActive.value
      ? t('production.lots.columns.stepGroup')
      : t('production.lots.columns.step', { n })
  }

  function stepGroupClass(n: number): string | undefined {
    return isColumnModeActive.value ? undefined : stepColumnClass(n)
  }

  const sourceGroupSpan = computed(() => (filtersStore.simpleMode ? 2 : 3))

  // One row per (lot, position) so rowGroupMode="rowspan" can merge the
  // lot-level columns. A lot without steps keeps one placeholder row.
  const flatPositionRows = computed<FlatPositionRow[]>(() => {
    if (!isColumnModeActive.value) return []
    return visibleLots.value.flatMap((lot): FlatPositionRow[] => {
      const groups = positionGroups(lot)
      if (groups.length === 0) {
        return [{ rowKey: `${lot.id}-none`, lotId: lot.id, lot, group: null }]
      }
      return groups.map((group) => ({
        rowKey: `${lot.id}-${group.positionId}`,
        lotId: lot.id,
        lot,
        group,
      }))
    })
  })

  const tableValue = computed<unknown[]>(() =>
    isColumnModeActive.value ? flatPositionRows.value : groupedLots.value,
  )

  // ── Column Mode row-block visuals ────────────────────────────────────
  //
  // OpenVue stripes and hovers per <tr>, which is wrong when a lot spans
  // several rows, so both are driven off the lot via :rowClass.

  const lotStripeParity = computed<Map<number, number>>(() => {
    const parity = new Map<number, number>()
    visibleLots.value.forEach((lot, index) => parity.set(lot.id, index % 2))
    return parity
  })

  const hoveredLotId = ref<number | null>(null)

  // DataTable emits no row-enter event, so the hovered lot is resolved by
  // delegation through each row's data-p-index.
  function onTableMouseOver(event: Event): void {
    if (!isColumnModeActive.value) return
    const row = (event.target as HTMLElement | null)?.closest?.('tr[data-p-index]')
    const index = row ? Number(row.getAttribute('data-p-index')) : Number.NaN
    hoveredLotId.value = Number.isNaN(index) ? null : (flatPositionRows.value[index]?.lotId ?? null)
  }

  // The row under the mouse or holding keyboard focus is highlighted alike,
  // so the card binds both pairs of events with one v-on.
  const rowHoverListeners = {
    mouseover: onTableMouseOver,
    focusin: onTableMouseOver,
    mouseleave: () => (hoveredLotId.value = null),
    focusout: () => (hoveredLotId.value = null),
  }

  function rowClass(data: unknown): string[] | undefined {
    if (!isColumnModeActive.value) return undefined
    const { lotId } = data as FlatPositionRow
    return [
      ...(isTableStripedEnabled.value && lotStripeParity.value.get(lotId) === 1
        ? ['lot-row--striped']
        : []),
      ...(hoveredLotId.value === lotId ? ['lot-row--hovered'] : []),
    ]
  }

  // Merged cells are centred against the lot's first row rather than the
  // whole block. CSS cannot express that offset, so it is measured per
  // render and applied as padding.
  const cardEl = ref<HTMLElement | null>(null)

  function alignMergedCells(): void {
    const merged = cardEl.value?.querySelectorAll<HTMLTableCellElement>(
      '.p-datatable-tbody > tr > td[rowspan]',
    )
    if (!merged?.length) return
    // jsdom's Range has no geometry.
    if (typeof document.createRange().getBoundingClientRect !== 'function') return
    // Clear the last pass's padding, then measure every cell before writing
    // any, so one cell's padding cannot inflate another's row.
    for (const cell of merged) cell.style.paddingTop = ''
    const offsets = new Map<HTMLTableCellElement, number>()
    for (const cell of merged) {
      const row = cell.parentElement
      if (!row) continue
      // The cell box spans the whole block, so content height comes from a
      // Range, which also covers bare text nodes.
      const range = document.createRange()
      range.selectNodeContents(cell)
      const contentHeight = range.getBoundingClientRect().height
      offsets.set(cell, (row.getBoundingClientRect().height - contentHeight) / 2)
    }
    for (const [cell, offset] of offsets) {
      const basePadding = Number.parseFloat(getComputedStyle(cell).paddingTop)
      if (offset > basePadding) cell.style.paddingTop = `${offset}px`
    }
  }

  function scheduleAlignMergedCells(): void {
    void nextTick(alignMergedCells)
  }

  watch([tableValue, isColumnModeActive, () => editStore.editMode, showManageSource], scheduleAlignMergedCells)
  onMounted(() => {
    scheduleAlignMergedCells()
    window.addEventListener('resize', scheduleAlignMergedCells)
  })
  onBeforeUnmount(() => window.removeEventListener('resize', scheduleAlignMergedCells))

  // Only set in Column Mode, where it makes OpenVue rowspan the lot-level cells.
  const groupField = computed(() => (isColumnModeActive.value ? 'lotId' : undefined))

  // Filtering is server-side; this object only exists because
  // filterDisplay="row" throws without it.
  const filters: DataTableFilterMeta = {
    lotId: { value: null, matchMode: FilterMatchMode.EQUALS },
  }

  function lotOf(data: unknown): LotSummaryResponse {
    return isColumnModeActive.value ? (data as FlatPositionRow).lot : (data as LotSummaryResponse)
  }

  function groupOf(data: unknown, n: number): LotStepGroup | undefined {
    if (isColumnModeActive.value) return (data as FlatPositionRow).group ?? undefined
    return positionGroups(lotOf(data))[n - 1]
  }

  return {
    statusOptions,
    priorityOptions,
    visibleLots,
    subheaderGroupRowsBy,
    maxPositionCount,
    isColumnModeActive,
    stepGroupCount,
    stepGroupHeader,
    stepGroupClass,
    sourceGroupSpan,
    flatPositionRows,
    tableValue,
    hoveredLotId,
    onTableMouseOver,
    rowHoverListeners,
    rowClass,
    cardEl,
    groupField,
    filters,
    lotOf,
    groupOf,
  }
}
