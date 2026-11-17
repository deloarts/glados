import { ref, watch } from 'vue'
import type { Ref } from 'vue'

import { createFiltersStore } from './createFiltersStore'
import type { FiltersStoreBase } from './createFiltersStore'

/** The filter field every demands filters store has, set while a Manage panel is open. */
export type DemandFilterFields = {
  notFullyAllocatedOnly: boolean
}

/** Maps each Manage panel name to the name of the store flag that shows it. */
export type DemandPanels = Record<string, string>

type PanelName<TPanels extends DemandPanels> = keyof TPanels & string

/**
 * The state every demands filters store adds to its filter fields: one flag
 * per Manage panel, the actions column toggle, the grouping and the panel
 * actions.
 */
export type DemandFiltersState<TPanels extends DemandPanels, TGroupBy extends string> = {
  [K in TPanels[keyof TPanels]]: Ref<boolean>
} & {
  showActions: Ref<boolean>
  groupBy: Ref<TGroupBy | null>
  setGroupBy: (value: TGroupBy) => void
  clearGroupBy: () => void
  toggleShowActions: () => void
  openPanel: (panel: PanelName<TPanels>, opts?: { keepSelection?: boolean }) => void
  closePanel: () => void
  togglePanel: (panel: PanelName<TPanels>) => void
}

export interface CreateDemandFiltersStoreConfig<
  TFields extends DemandFilterFields & Record<string, unknown>,
  TPanels extends DemandPanels,
  TGroupBy extends string,
  TExtra extends Record<string, unknown>,
> {
  /** Field defaults as a factory, so `clearAll()` never hands back a shared array. */
  defaults: () => TFields
  /** Array fields need a length check, since the default equality compares by reference. */
  isActive: (fields: TFields) => boolean
  /** For example `{ orders: 'showManageOrderPanel', stock: 'showManageStockPanel' }`. */
  panels: TPanels
  /** The table's selection store, which opening and closing a panel clears. */
  useSelectionStore: () => { clearSelection: () => void }
  /** Family-specific extras built on top of the shared state. */
  extend?: (state: DemandFiltersState<TPanels, TGroupBy>) => TExtra
}

/**
 * Builds the filters store of a demands table: the family's filter fields
 * and sorting through `createFiltersStore`, plus the Manage panels, the
 * actions column toggle and the grouping that the bought, made and source
 * item demand tables share. Give every generic explicitly, for the reasons
 * `createFiltersStore` names.
 */
export function createDemandFiltersStore<
  TFields extends DemandFilterFields & Record<string, unknown>,
  TSortField extends string,
  TGroupBy extends string,
  TPanels extends DemandPanels,
  TExtra extends Record<string, unknown> = Record<never, never>,
>(id: string, config: CreateDemandFiltersStoreConfig<TFields, TPanels, TGroupBy, TExtra>) {
  function extend(base: FiltersStoreBase<TFields, TSortField, true>) {
    const selectionStore = config.useSelectionStore()
    const panelNames = Object.keys(config.panels) as PanelName<TPanels>[]

    const panelFlags = {} as Record<PanelName<TPanels>, Ref<boolean>>
    for (const panel of panelNames) {
      panelFlags[panel] = ref(false)
    }
    const showActions = ref(false)
    const groupBy = ref(null) as Ref<TGroupBy | null>

    // Any open panel narrows the list on every open.
    const notFullyAllocatedOnly = base.notFullyAllocatedOnly as Ref<boolean>
    watch(
      panelNames.map((panel) => panelFlags[panel]),
      (open) => {
        notFullyAllocatedOnly.value = open.some(Boolean)
      },
    )

    function setGroupBy(value: TGroupBy): void {
      groupBy.value = groupBy.value === value ? null : value
    }

    function clearGroupBy(): void {
      groupBy.value = null
    }

    function toggleShowActions(): void {
      showActions.value = !showActions.value
    }

    // The panels share one selection and are mutually exclusive. Opening or
    // closing clears the selection unless the caller carries it over, as the
    // context menu entries do.
    function openPanel(panel: PanelName<TPanels>, opts?: { keepSelection?: boolean }): void {
      for (const name of panelNames) {
        panelFlags[name].value = name === panel
      }
      if (!opts?.keepSelection) {
        selectionStore.clearSelection()
      }
    }

    function closePanel(): void {
      for (const name of panelNames) {
        panelFlags[name].value = false
      }
      selectionStore.clearSelection()
    }

    function togglePanel(panel: PanelName<TPanels>): void {
      if (panelFlags[panel].value) {
        closePanel()
      } else {
        openPanel(panel)
      }
    }

    const flagState = Object.fromEntries(
      panelNames.map((panel) => [config.panels[panel], panelFlags[panel]]),
    )

    const state = {
      ...flagState,
      showActions,
      groupBy,
      setGroupBy,
      clearGroupBy,
      toggleShowActions,
      openPanel,
      closePanel,
      togglePanel,
    } as DemandFiltersState<TPanels, TGroupBy>

    return {
      state: { ...state, ...config.extend?.(state) } as DemandFiltersState<TPanels, TGroupBy> &
        TExtra,
      onClear: () => {
        groupBy.value = null
      },
    }
  }

  return createFiltersStore<
    TFields,
    TSortField,
    true,
    DemandFiltersState<TPanels, TGroupBy> & TExtra
  >(id, {
    defaults: config.defaults,
    isActive: config.isActive,
    sortable: true,
    extend,
  })
}
