// Maps a machine key to the i18n prefix that already translates its states
// elsewhere in the app. An unknown key or value falls back to a humanized
// raw value.
const STATUS_LABEL_PREFIXES: Record<string, string> = {
  order_status: 'orders.status',
  order_item_status: 'orders.items.status',
  production_order_status: 'production.lots.orderStatus',
  lot_status: 'production.lots.status',
  lot_position_kind: 'production.lots.positionKind',
  lot_position_status: 'production.lots.positionStatus',
  bought_item_demand_status: 'boughtItems.demands.status',
  made_item_demand_status: 'madeItems.demands.status',
  source_item_demand_status: 'sourceItems.demands.status',
  catalogue_item_status: 'boughtItems.catalogue.status',
  project_status: 'resources.projects.status',
}

type Translate = (key: string) => string
type HasKey = (key: string) => boolean

// 'partially_planned' becomes 'Partially Planned'; only has to beat the raw
// enum value.
function humanize(value: string): string {
  return value
    .split('_')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

export function resolveStateLabel(
  t: Translate,
  te: HasKey,
  machineKey: string,
  value: string,
): string {
  const prefix = STATUS_LABEL_PREFIXES[machineKey]
  if (prefix) {
    const path = `${prefix}.${value}`
    if (te(path)) return t(path)
  }
  return humanize(value)
}

/** The label of a lifecycle action, e.g. "force_complete". */
export function resolveActionLabel(t: Translate, te: HasKey, action: string): string {
  const path = `stateMachines.actions.${action}`
  return te(path) ? t(path) : humanize(action)
}

/**
 * The translated text of a catalogue row, `path` relative to the
 * stateMachines block (e.g. "rows.lot_status.r1"). The backend's own text is
 * the fallback for a key the locale does not have yet; a backend test keeps
 * every key present in both locales.
 */
export function resolveRowText(t: Translate, te: HasKey, path: string, fallback: string): string {
  const key = `stateMachines.${path}`
  return te(key) ? t(key) : fallback
}

/** The label of a transition's trigger, e.g. "deliver_all". */
export function resolveTriggerLabel(t: Translate, te: HasKey, trigger: string): string {
  const path = `stateMachines.triggers.${trigger}`
  return te(path) ? t(path) : humanize(trigger)
}

/** The name of a machine's record, e.g. "Order Line" for "order_item_status". */
export function resolveMachineLabel(t: Translate, te: HasKey, machineKey: string): string {
  const path = `stateMachines.machines.${machineKey}`
  return te(path) ? t(path) : humanize(machineKey)
}
