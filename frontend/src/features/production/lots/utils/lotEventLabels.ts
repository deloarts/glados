import type { LotEventResponse, LotEventType } from '../../types/productionLotsResponse'

// Mirrors the backend's LotEventType enum (lot_event_type.py). One icon +
// i18n label per event, grouped visually by which aggregate they mutate.
export const LOT_EVENT_ICONS: Record<LotEventType, string> = {
  lot_created: 'mdi-plus-circle-outline',
  lot_updated: 'mdi-pencil',
  lot_material_source_switched: 'mdi-swap-horizontal',
  lot_canceled: 'mdi-close-circle-outline',
  lot_completed: 'mdi-check-circle-outline',
  lot_held: 'mdi-pause-circle-outline',
  lot_resumed: 'mdi-play-circle-outline',
  lot_scrapped: 'mdi-delete-circle-outline',
  lot_status_changed: 'mdi-swap-vertical-circle-outline',
  lot_source_approved: 'mdi-thumb-up-outline',
  lot_source_rejected: 'mdi-thumb-down-outline',
  lot_closed_short: 'mdi-content-cut',
  rework_lot_created: 'mdi-wrench-outline',
  replacement_lot_created: 'mdi-recycle',
  positions_regrouped: 'mdi-group',
  position_appended: 'mdi-plus-box-outline',
  position_assigned_external: 'mdi-truck-outline',
  position_unassigned_external: 'mdi-truck-remove-outline',
  position_provision_recorded: 'mdi-truck-fast-outline',
  position_assigned_internal: 'mdi-robot-industrial-outline',
  step_added: 'mdi-plus-box-outline',
  step_updated: 'mdi-pencil',
  step_deleted: 'mdi-delete-outline',
  steps_reordered: 'mdi-sort',
  order_started: 'mdi-play',
  order_paused: 'mdi-pause',
  order_canceled: 'mdi-close-circle-outline',
  order_split: 'mdi-call-split',
  order_merged: 'mdi-call-merge',
  order_completion_recorded: 'mdi-check-bold',
  order_completion_reversed: 'mdi-undo-variant',
  inspection_recorded: 'mdi-check-decagram',
  pieces_scrapped: 'mdi-delete-alert-outline',
  replacement_skipped: 'mdi-cancel',
  pieces_lost_at_receipt: 'mdi-package-variant-remove',
  wip_dropped: 'mdi-tray-remove',
  raw_material_left_over: 'mdi-package-variant',
}

// Shown for an event type this map does not know yet.
export const FALLBACK_LOT_EVENT_ICON = 'mdi-information-outline'

export function lotEventLabelKey(eventType: string): string {
  return `production.lots.detail.audit.events.${eventType}`
}

export function lotEventIcon(eventType: string): string {
  const icons: Record<string, string | undefined> = LOT_EVENT_ICONS
  return icons[eventType] ?? FALLBACK_LOT_EVENT_ICON
}

interface LotEventLabelI18n {
  t: (key: string) => string
  te: (key: string) => boolean
}

// The event's translated label, or its type in words while no translation
// exists, so a new event type never shows a raw message key.
export function lotEventLabel(eventType: string, { t, te }: LotEventLabelI18n): string {
  const key = lotEventLabelKey(eventType)
  return te(key) ? t(key) : humanizeLotEventType(eventType)
}

export function humanizeLotEventType(eventType: string): string {
  return eventType
    .split('_')
    .filter((word) => word.length > 0)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

// Who did it, for display: the actor's full name, a snapshot taken when the
// event was recorded.
export function lotEventActorName(event: LotEventResponse): string {
  return event.actor_full_name
}
