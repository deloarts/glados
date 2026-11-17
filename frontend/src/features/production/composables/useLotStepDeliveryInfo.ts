import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Ref } from 'vue'

import { instantToPickerDate, toLocalDayStart, toWallClockDate } from '@/core/utils/dates'
import { findStepNeighbors } from '../utils/lotStepNeighbors'
import { stepMethodLabel } from '../utils/lotStepDisplay'

import type {
  LotSummaryPositionResponse,
  LotSummaryResponse,
  LotSummaryStepResponse,
} from '../types/productionLotsResponse'
import type { ScheduleConflict } from '../types/productionOrdersResponse'

// Who or what produced PlannedInfo.date, for the attribution tooltip.
// `kind` is null when there is no date; unused fields are null, never
// undefined.
export interface PlannedAttribution {
  kind: 'external_typed' | 'external_forecast' | 'manual_pinned' | 'auto_planner' | 'actual' | null
  personName: string | null
  orderId: number | null
  orderNumber: string | null
  machineName: string | null
  poolName: string | null
  plannedPickupDate: Date | null
  plannedDeliveryDate: Date | null
  // External forecasts only: the lead time and its source.
  leadDays: number | null
  leadDaysSource: string | null
}

const NO_ATTRIBUTION: PlannedAttribution = {
  kind: null,
  personName: null,
  orderId: null,
  orderNumber: null,
  machineName: null,
  poolName: null,
  plannedPickupDate: null,
  plannedDeliveryDate: null,
  leadDays: null,
  leadDaysSource: null,
}

// What governs an internal order's earliest start (see the backend's
// explain_earliest_start); null when nothing was resolved.
export interface EarliestStartInfo {
  reason: string | null
  date: Date | null
}

const NO_EARLIEST_START: EarliestStartInfo = { reason: null, date: null }

// The current plan: the scheduler's date for internal work, the supplier's
// expected delivery for external. Anything asking "when will this happen"
// reads this, not ConfirmedDeliveryInfo.
export interface PlannedInfo {
  date: Date | null
  // Actual, else planned start, so a multi-day job does not look like a
  // same-day one. Null for purely external positions.
  startDate: Date | null
  // A confirmed/arrived date (everything that contributed to it is done),
  // as opposed to a projected/expected one that can still move.
  isFinal: boolean
  // A projected date already in the past: a slipped plan.
  isOverdue: boolean
  note: string | null
  // A coarse attention signal for the lots table, never blocking.
  conflicts: ScheduleConflict[]
  // A person's name, "Auto-planner", or null without a date.
  plannedByLabel: string | null
  // External pickup, usually null. isReady distinguishes the confirmed
  // ready date from the supplier's expected one.
  pickup: { date: Date; isReady: boolean } | null
  // Who or what set the shown `date` and why, see PlannedAttribution.
  // Never itself null; `kind` is null in its place when nothing applies.
  attribution: PlannedAttribution
  // Internal orders only.
  earliestStart: EarliestStartInfo
}

// Labels a box in the planned date dialog's material flow.
export interface PlannedDateStepInfo {
  fabricationMethodName: string
}

// The lot and step context around the edited order, for the planned date
// dialog.
export interface PlannedDateContext {
  lotId: number
  madeItem: {
    id: number
    partNumber: string
    revision: string
    articleName: string
  }
  thisStep: PlannedDateStepInfo
  // Null at either end of the sequence.
  prevStep: PlannedDateStepInfo | null
  nextStep: PlannedDateStepInfo | null
}

// Only a single queued or paused internal order, or a single undelivered
// order item, has one editable date; split and mixed positions return null.
export type PlannedDateEditTarget =
  | ({
      kind: 'internal'
      orderId: number
      // The edit version of the order or the line as listed, which the edit
      // sends.
      editVersion: number
      currentPlannedStart: string | null
      currentPlannedEnd: string | null
    } & PlannedDateContext)
  | ({
      kind: 'external'
      orderId: number
      itemId: number
      editVersion: number
      quantity: number
      unit: string
      itemsPerUnit: number
      currentExpectedDeliveryDate: string | null
    } & PlannedDateContext)
  | null

// The factual counterpart to PlannedInfo: only confirmed dates, never a
// projection, so it never repeats the planned column.
export interface ConfirmedDeliveryInfo {
  date: Date | null
  note: string | null
}

// A step's source, split into a clickable order and plain machine names.
export interface SourceOrderInfo {
  orderId: number | null
  orderNumber: string | null
  machineNames: string[]
}

interface DateEntry {
  date: Date | null
  startDate: Date | null
  isFinal: boolean
  // Only set when the entry is worth a note on its own, e.g. a partial
  // delivery.
  note: string | null
  plannedByLabel: string | null
  attribution: PlannedAttribution
  earliestStart: EarliestStartInfo
}

// Resolves each lot's per-step planned and delivery dates from the
// positions the lots list already carries, without fetching. External
// steps use the order item's dates, internal steps the orders' actual end
// or the scheduler's planned end (never a client guess), and mixed steps
// the later of both.
export function useLotStepDeliveryInfo(lots: Ref<LotSummaryResponse[]>) {
  const { t } = useI18n()

  const lotById = computed(() => new Map(lots.value.map((lot) => [lot.id, lot])))

  // Keyed by lot and position, so a stale id from a previous page never
  // resolves against the current lot.
  const positionByKey = computed(() => {
    const map = new Map<string, LotSummaryPositionResponse>()
    for (const lot of lots.value) {
      for (const position of lot.positions ?? []) {
        map.set(`${lot.id}-${position.id}`, position)
      }
    }
    return map
  })

  function positionFor(lotId: number, positionId: number): LotSummaryPositionResponse | undefined {
    return positionByKey.value.get(`${lotId}-${positionId}`)
  }

  // Late when any order carries past_target_date, reusing the conflicts.
  function lotHasPastTargetDateConflict(lotId: number): boolean {
    const lot = lotById.value.get(lotId)
    if (!lot) return false
    return (lot.positions ?? []).some((p) =>
      (p.production_orders ?? []).some(
        (o) => o.status !== 'canceled' && (o.conflicts ?? []).includes('past_target_date'),
      ),
    )
  }

  function externalEntry(position: LotSummaryPositionResponse): DateEntry {
    // Without an order item only the position's own expected date exists.
    if (position.order_item_id === null) {
      return {
        date: position.expected_delivery_date
          ? toLocalDayStart(position.expected_delivery_date)
          : null,
        startDate: null,
        isFinal: false,
        note: null,
        plannedByLabel: null,
        attribution: NO_ATTRIBUTION,
        earliestStart: NO_EARLIEST_START,
      }
    }
    // External dates come from a person, except the forecast below.
    const plannedByLabel = position.ordered_by_name
    const orderId = position.order_id ?? null
    const orderNumber = position.order_number || null
    if (position.order_item_status === 'delivered') {
      return {
        date: position.delivery_date ? toLocalDayStart(position.delivery_date) : null,
        startDate: null,
        isFinal: true,
        note:
          position.delivery_record_count > 1
            ? t('production.lots.deliveryDate.deliveredInShipments', {
                n: position.delivery_record_count,
              })
            : null,
        plannedByLabel,
        attribution: { ...NO_ATTRIBUTION, kind: 'actual', orderId, orderNumber },
        earliestStart: NO_EARLIEST_START,
      }
    }
    const partialNote =
      (position.order_item_quantity_delivered ?? 0) > 0
        ? t('production.lots.deliveryDate.partiallyDelivered', {
            delivered: position.order_item_quantity_delivered,
            total: position.order_item_quantity,
          })
        : null
    if (position.expected_delivery_date) {
      return {
        date: toLocalDayStart(position.expected_delivery_date),
        startDate: null,
        isFinal: false,
        note: partialNote,
        plannedByLabel,
        attribution: {
          ...NO_ATTRIBUTION,
          kind: 'external_typed',
          personName: plannedByLabel,
          orderId,
          orderNumber,
        },
        earliestStart: NO_EARLIEST_START,
      }
    }
    // Without a typed date, the backend forecast is shown.
    if (position.planned_delivery_date) {
      return {
        date: toLocalDayStart(position.planned_delivery_date),
        startDate: null,
        isFinal: false,
        note: partialNote,
        plannedByLabel: t('production.lots.plannedDate.autoPlanner'),
        attribution: {
          ...NO_ATTRIBUTION,
          kind: 'external_forecast',
          orderId,
          orderNumber,
          plannedPickupDate: position.planned_pickup_date
            ? toLocalDayStart(position.planned_pickup_date)
            : null,
          plannedDeliveryDate: toLocalDayStart(position.planned_delivery_date),
          leadDays: position.lead_days ?? null,
          leadDaysSource: position.lead_days_source ?? null,
        },
        earliestStart: NO_EARLIEST_START,
      }
    }
    return {
      date: null,
      startDate: null,
      isFinal: false,
      note: partialNote,
      plannedByLabel,
      attribution: NO_ATTRIBUTION,
      earliestStart: NO_EARLIEST_START,
    }
  }

  // Null whenever neither pickup field is set.
  function pickupEntryFor(position: LotSummaryPositionResponse): PlannedInfo['pickup'] {
    if (position.order_item_id === null) return null
    if (position.ready_for_pickup_date) {
      return { date: toLocalDayStart(position.ready_for_pickup_date), isReady: true }
    }
    if (position.expected_pickup_date) {
      return { date: toLocalDayStart(position.expected_pickup_date), isReady: false }
    }
    return null
  }

  function internalEntries(position: LotSummaryPositionResponse): DateEntry[] {
    return (position.production_orders ?? [])
      .filter((po) => po.status !== 'canceled')
      .map((po) => {
        // null planned_by_name means the scheduler computed the date.
        const plannedByLabel = po.planned_by_name ?? t('production.lots.plannedDate.autoPlanner')
        // Actual start once begun, else planned start.
        const startDate = po.actual_start
          ? toWallClockDate(po.actual_start)
          : po.planned_start
            ? toWallClockDate(po.planned_start)
            : null
        const machineName = po.machine_internal_name || null
        const poolName = po.machine_pool_name || null
        if (po.status === 'completed') {
          return {
            date: po.actual_end ? toWallClockDate(po.actual_end) : null,
            startDate,
            isFinal: true,
            note: null,
            plannedByLabel,
            attribution: { ...NO_ATTRIBUTION, kind: 'actual', orderId: po.id },
            // A finished order has nothing left to explain about its start.
            earliestStart: NO_EARLIEST_START,
          }
        }
        // An order without planned_end contributes no date.
        return {
          date: po.planned_end ? toWallClockDate(po.planned_end) : null,
          startDate,
          isFinal: false,
          note: null,
          plannedByLabel,
          attribution: po.planned_by_name
            ? {
                ...NO_ATTRIBUTION,
                kind: 'manual_pinned',
                personName: po.planned_by_name,
                orderId: po.id,
                machineName,
                poolName,
              }
            : {
                ...NO_ATTRIBUTION,
                kind: 'auto_planner',
                orderId: po.id,
                machineName,
                poolName,
              },
          earliestStart: {
            reason: po.earliest_start_reason ?? null,
            date: po.earliest_start_date ? toLocalDayStart(po.earliest_start_date) : null,
          },
        }
      })
  }

  function stepInfo(step: LotSummaryStepResponse): PlannedDateStepInfo {
    return { fabricationMethodName: stepMethodLabel(step) }
  }

  function contextFor(lot: LotSummaryResponse, step: LotSummaryStepResponse): PlannedDateContext {
    const { prevStep, nextStep } = findStepNeighbors(lot.steps ?? [], step.id)
    return {
      lotId: lot.id,
      madeItem: {
        id: lot.made_item_id,
        partNumber: lot.made_item_part_number,
        revision: lot.made_item_revision,
        articleName: lot.made_item_article_name,
      },
      thisStep: stepInfo(step),
      prevStep: prevStep ? stepInfo(prevStep) : null,
      nextStep: nextStep ? stepInfo(nextStep) : null,
    }
  }

  function editTargetFor(lotId: number, stepId: number): PlannedDateEditTarget {
    const lot = lotById.value.get(lotId)
    const step = lot?.steps?.find((s) => s.id === stepId)
    if (!lot || !step) return null
    const position = positionFor(lotId, step.position_id)
    if (!position) return null
    const context = contextFor(lot, step)

    if (position.kind === 'internal') {
      const active = (position.production_orders ?? []).filter((po) => po.status !== 'canceled')
      if (active.length !== 1) return null
      const order = active[0]!
      if (order.status !== 'queued' && order.status !== 'paused') return null
      return {
        kind: 'internal',
        orderId: order.id,
        editVersion: order.edit_version,
        currentPlannedStart: order.planned_start,
        currentPlannedEnd: order.planned_end,
        ...context,
      }
    }

    if (position.kind === 'external') {
      if (
        position.order_id === null ||
        position.order_item_id === null ||
        position.order_item_status === 'delivered'
      ) {
        return null
      }
      return {
        kind: 'external',
        orderId: position.order_id,
        itemId: position.order_item_id,
        editVersion: position.order_item_edit_version,
        quantity: position.order_item_quantity ?? 0,
        unit: position.order_item_unit,
        itemsPerUnit: position.order_item_items_per_unit,
        currentExpectedDeliveryDate: position.expected_delivery_date,
        ...context,
      }
    }

    return null
  }

  function positionConflicts(position: LotSummaryPositionResponse): ScheduleConflict[] {
    const seen = new Set<ScheduleConflict>()
    for (const po of position.production_orders ?? []) {
      if (po.status === 'canceled') continue
      for (const conflict of po.conflicts ?? []) seen.add(conflict)
    }
    return [...seen]
  }

  function plannedDateFor(position: LotSummaryPositionResponse | undefined): PlannedInfo {
    if (!position || position.kind === 'unassigned')
      return {
        date: null,
        startDate: null,
        isFinal: false,
        isOverdue: false,
        note: null,
        conflicts: [],
        plannedByLabel: null,
        pickup: null,
        attribution: NO_ATTRIBUTION,
        earliestStart: NO_EARLIEST_START,
      }

    const external =
      position.kind === 'external' || position.kind === 'mixed' ? externalEntry(position) : null
    const internal =
      position.kind === 'internal' || position.kind === 'mixed' ? internalEntries(position) : []
    const conflicts = positionConflicts(position)
    const pickup =
      position.kind === 'external' || position.kind === 'mixed' ? pickupEntryFor(position) : null

    const allEntries = external ? [external, ...internal] : internal
    const known = allEntries.filter((e): e is DateEntry & { date: Date } => e.date !== null)
    if (known.length === 0)
      return {
        date: null,
        startDate: null,
        isFinal: false,
        isOverdue: false,
        note: null,
        conflicts,
        plannedByLabel: null,
        pickup,
        attribution: NO_ATTRIBUTION,
        earliestStart: NO_EARLIEST_START,
      }

    const latest = known.reduce((a, b) => (b.date.getTime() > a.date.getTime() ? b : a))
    // The earliest known start, when work on any part begins.
    const knownStarts = allEntries.map((e) => e.startDate).filter((d): d is Date => d !== null)
    const startDate =
      knownStarts.length > 0
        ? knownStarts.reduce((a, b) => (b.getTime() < a.getTime() ? b : a))
        : null
    const isFinal = allEntries.length === known.length && allEntries.every((e) => e.isFinal)
    // Only a projected date can be overdue; a final date in the past is history.
    // The dates sit on the tenant's wall clock, so "now" does too.
    const isOverdue = !isFinal && latest.date.getTime() < instantToPickerDate(new Date()).getTime()

    const noteParts: string[] = []
    if (external?.note) noteParts.push(external.note)
    if (internal.length > 1) {
      noteParts.push(t('production.lots.deliveryDate.splitAcrossOrders', { n: internal.length }))
    }
    if (position.kind === 'mixed' && external && internal.length > 0) {
      noteParts.push(t('production.lots.deliveryDate.mixedSource'))
    }

    return {
      date: latest.date,
      startDate,
      isFinal,
      isOverdue,
      note: noteParts.length > 0 ? noteParts.join(' · ') : null,
      conflicts,
      plannedByLabel: latest.plannedByLabel,
      pickup,
      // The attribution explains whichever entry won the comparison.
      attribution: latest.attribution,
      earliestStart: latest.earliestStart,
    }
  }

  // Derived from the same computation, so both columns agree on the latest
  // entry. Confirmed dates only.
  function confirmedDeliveryFor(planned: PlannedInfo): ConfirmedDeliveryInfo {
    if (!planned.date || !planned.isFinal) return { date: null, note: null }
    return { date: planned.date, note: planned.note }
  }

  // Split so the order number can link to its order while machine names
  // stay plain text.
  function sourceOrderInfoFor(
    position: LotSummaryPositionResponse | undefined,
  ): SourceOrderInfo | null {
    if (!position || position.kind === 'unassigned') return null

    const orderId =
      position.kind === 'external' || position.kind === 'mixed' ? (position.order_id ?? null) : null
    const orderNumber =
      position.kind === 'external' || position.kind === 'mixed'
        ? position.order_number || null
        : null

    const machineNames =
      position.kind === 'internal' || position.kind === 'mixed'
        ? [
            ...new Set(
              (position.production_orders ?? [])
                .filter((po) => po.status !== 'canceled')
                .map(
                  (po) =>
                    po.machine_internal_name ||
                    po.machine_pool_name ||
                    t('production.lots.source.notAssigned'),
                ),
            ),
          ]
        : []

    if (orderId === null && machineNames.length === 0) return null
    return { orderId, orderNumber, machineNames }
  }

  return {
    positionFor,
    plannedDateFor,
    confirmedDeliveryFor,
    editTargetFor,
    sourceOrderInfoFor,
    lotHasPastTargetDateConflict,
  }
}
