import { anyHasAction, hasAction } from '@/core/utils/lifecycleActions'
import type { HasActions, LifecycleAction } from '@/core/utils/lifecycleActions'
import type { Translate } from '@/core/i18n'

import type { MenuItem } from 'openvue/menuitem'

/** The status a user sets by hand from the context menu. */
export type DemandMenuStatus = 'fulfilled' | 'canceled'

/** The family's own Manage panel, orders for bought and source items, lots for made items. */
export interface DemandMenuPanelEntry<TDemand> {
  label: string
  icon: string
  disabled: boolean
  /** Why the entry is disabled, such as the missing permission, shown as its title. */
  disabledReason?: string
  /**
   * The server action a single demand must offer for the entry to show. A
   * demand without it, such as a fulfilled one, cannot take what the panel
   * would add, so its entry is hidden rather than disabled.
   */
  action?: LifecycleAction
  /** Opens the panel on the current selection, for several targets. */
  open: () => void
  /** Adds the one target to the selection and opens the panel. */
  addDemand: (demand: TDemand) => void
}

export interface DemandContextMenuConfig<TDemand extends HasActions & { public_id: string }> {
  t: Translate
  /** The family's demands namespace, such as `boughtItems.demands`. */
  keyPrefix: string
  /** The right-clicked row, or the selection it belongs to. */
  targets: TDemand[]
  canEdit: boolean
  canSetStatus: boolean
  /** Why Set Status is disabled without the rights, shown as its title. */
  setStatusDisabledReason?: string
  /** Why one demand's Canceled status entry is disabled, shown as its title. */
  cancelDisabledReason?: (demand: TDemand) => string
  canWriteBuckets: boolean
  canWriteAllocations: boolean
  /** Adds the disabled "Copy" placeholder below Edit. */
  showCopyPlaceholder: boolean
  bucketItems: (targets: TDemand[]) => MenuItem[]
  openDetail: (demand: TDemand) => void
  setStatus: (demand: TDemand, status: DemandMenuStatus) => unknown
  fulfilTargets: (targets: TDemand[]) => unknown
  requestBulkCancel: (targets: TDemand[]) => unknown
  panel: DemandMenuPanelEntry<TDemand>
  /** The Manage Quotes panel, for the families a quote request asks for. */
  quotePanel?: DemandMenuPanelEntry<TDemand>
  /** Opens the Manage Stock panel on the current selection. */
  openStockPanel: () => void
  /** The family's entries between the bucket entry and its panel entry. */
  singleEntries: (demand: TDemand) => MenuItem[]
  /** Entries the family adds right before Copy UUID, ending in a separator. */
  trailingEntries?: (demand: TDemand) => MenuItem[]
  copyToClipboard: (text: string) => unknown
}

/**
 * The context menu of the demand tables. Several targets get the status,
 * panel and bucket entries that act on all of them. One target gets edit,
 * status and bucket, then the family's own entries, its panel entry and
 * Copy UUID.
 */
export function demandContextMenu<TDemand extends HasActions & { public_id: string }>(
  config: DemandContextMenuConfig<TDemand>,
): MenuItem[] {
  const { t, keyPrefix: p, targets } = config
  if (targets.length === 0) return []

  const bucketEntry = (bucketTargets: TDemand[]): MenuItem => ({
    label: t(`${p}.contextMenu.addToBucket`),
    icon: 'mdi mdi-bucket-outline',
    disabled: !config.canWriteBuckets,
    items: config.bucketItems(bucketTargets),
  })

  const statusEntry = (fulfil: MenuItem, cancel: MenuItem): MenuItem => ({
    label: t(`${p}.contextMenu.setStatus`),
    icon: 'mdi mdi-flag-outline',
    disabled: !config.canSetStatus,
    title: config.setStatusDisabledReason || undefined,
    items: [
      {
        label: t(`${p}.status.fulfilled`),
        icon: 'mdi mdi-check-circle-outline',
        ...fulfil,
      },
      {
        label: t(`${p}.status.canceled`),
        icon: 'mdi mdi-close-circle-outline',
        ...cancel,
      },
    ],
  })

  const entryItem = (entry: DemandMenuPanelEntry<TDemand>, command: () => void): MenuItem => ({
    label: entry.label,
    icon: entry.icon,
    disabled: entry.disabled,
    title: entry.disabledReason || undefined,
    command,
  })

  // A single demand that lacks the entry's action leaves the entry out.
  const offers = (entry: DemandMenuPanelEntry<TDemand>, demand?: TDemand): boolean =>
    !demand || !entry.action || hasAction(demand, entry.action)

  const panelEntries = (command: () => void, demand?: TDemand): MenuItem[] =>
    offers(config.panel, demand) ? [entryItem(config.panel, command)] : []

  const quoteEntries = (
    command: (entry: DemandMenuPanelEntry<TDemand>) => void,
    demand?: TDemand,
  ): MenuItem[] => {
    const entry = config.quotePanel
    if (!entry || !offers(entry, demand)) return []
    return [entryItem(entry, () => command(entry))]
  }

  if (targets.length > 1) {
    return [
      {
        label: t(`${p}.contextMenu.selectedCount`, { count: targets.length }),
        disabled: true,
      },
      { separator: true },
      statusEntry(
        {
          disabled: !anyHasAction(targets, 'fulfil'),
          command: () => config.fulfilTargets(targets),
        },
        {
          disabled: !anyHasAction(targets, 'cancel'),
          command: () => config.requestBulkCancel(targets),
        },
      ),
      { separator: true },
      ...panelEntries(config.panel.open),
      ...quoteEntries((entry) => entry.open()),
      {
        label: t(`${p}.contextMenu.fulfillFromStock`),
        icon: 'mdi mdi-package-variant-closed',
        disabled: !config.canWriteAllocations,
        command: config.openStockPanel,
      },
      bucketEntry(targets),
    ]
  }

  const demand = targets[0]!

  return withoutDoubleSeparators([
    {
      label: t(`${p}.contextMenu.edit`),
      icon: 'mdi mdi-pencil',
      disabled: !config.canEdit,
      command: () => config.openDetail(demand),
    },
    ...(config.showCopyPlaceholder
      ? [
          {
            label: t(`${p}.contextMenu.copy`),
            icon: 'mdi mdi-content-copy',
            disabled: true,
            title: t('common.notImplemented'),
          },
        ]
      : []),
    { separator: true },
    statusEntry(
      {
        disabled: !hasAction(demand, 'fulfil'),
        command: () => config.setStatus(demand, 'fulfilled'),
      },
      {
        disabled: !hasAction(demand, 'cancel'),
        title: hasAction(demand, 'cancel')
          ? undefined
          : config.cancelDisabledReason?.(demand) || undefined,
        command: () => config.setStatus(demand, 'canceled'),
      },
    ),
    bucketEntry([demand]),
    { separator: true },
    ...config.singleEntries(demand),
    { separator: true },
    ...panelEntries(() => config.panel.addDemand(demand), demand),
    ...quoteEntries((entry) => entry.addDemand(demand), demand),
    { separator: true },
    ...(config.trailingEntries?.(demand) ?? []),
    {
      label: t('common.copyUuid'),
      icon: 'mdi mdi-content-copy',
      command: () => config.copyToClipboard(demand.public_id),
    },
  ])
}

// Entries a demand's state leaves out can leave two separators in a row.
function withoutDoubleSeparators(items: MenuItem[]): MenuItem[] {
  return items.filter((item, i) => !(item.separator && items[i - 1]?.separator))
}
