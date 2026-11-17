/**
 * Shape and payload conversions for the demand fields every bought/made/
 * source-item create and detail form shares: quantity, unit, items_per_unit,
 * high_priority, notify_on_delivery, desired_delivery_date and note. Each
 * family layers its own extra fields (made items' alteration pair, for
 * instance) on top of these before sending a request.
 */
import { dateToParam as formatDate } from '@/core/utils/dates'

// eslint-disable-next-line no-restricted-syntax -- form state shared by the demand forms, with dates as Date
export interface DemandCommonEditFields {
  quantity: number
  unit: string
  items_per_unit: number
  high_priority: boolean
  notify_on_delivery: boolean
  desired_delivery_date: Date | null
  note: string
}

// eslint-disable-next-line no-restricted-syntax -- form state shared by the demand forms, with dates as Date
export interface DemandCommonCreateFields {
  quantity: number | null
  unit: string
  items_per_unit: number
  high_priority: boolean
  notify_on_delivery: boolean
  desired_delivery_date: Date | null
  note: string
}

// eslint-disable-next-line no-restricted-syntax -- the fields every demand create and update body shares
export interface DemandCommonPayload {
  quantity: number
  unit: string
  items_per_unit: number
  high_priority: boolean
  notify_on_delivery: boolean
  desired_delivery_date: string | null
  note: string | null
}

/** The response fields `demandCommonEditFieldsFromResponse` reads. */
// eslint-disable-next-line no-restricted-syntax -- a structural constraint every demand response must satisfy
export interface DemandResponseCommonFields {
  quantity: number
  unit: string
  items_per_unit: number
  high_priority: boolean
  notify_on_delivery: boolean
  desired_delivery_date: string | null
  note: string | null | undefined
}

export function parseDemandDate(value: string | null): Date | null {
  return value ? new Date(value) : null
}

/** Builds a detail dialog's edit-form fields from an existing demand. */
export function demandCommonEditFieldsFromResponse(
  d: DemandResponseCommonFields,
): DemandCommonEditFields {
  return {
    quantity: d.quantity,
    unit: d.unit,
    items_per_unit: d.items_per_unit,
    high_priority: d.high_priority,
    notify_on_delivery: d.notify_on_delivery,
    desired_delivery_date: parseDemandDate(d.desired_delivery_date),
    note: d.note ?? '',
  }
}

/**
 * Builds a create form's default fields. `defaultUnit` is passed in
 * because the unit code list is bought-items-owned, not something this
 * shared module can import.
 */
export function createDemandCommonCreateFields(
  defaultUnit: string,
  quantity: number | null = null,
): DemandCommonCreateFields {
  return {
    quantity,
    unit: defaultUnit,
    items_per_unit: 1,
    high_priority: false,
    notify_on_delivery: false,
    desired_delivery_date: null,
    note: '',
  }
}

/**
 * The base validity check every create form applies before its own extra
 * fields (an item/project pick, a lot pick, an alteration target).
 */
export function isDemandCommonCreateFieldsValid(f: DemandCommonCreateFields): boolean {
  return f.quantity !== null && f.quantity > 0 && f.unit.trim().length > 0
}

/**
 * Converts either a create or an edit form's common fields into the
 * request payload shape. Assumes quantity has already been validated as
 * non-null on the create-form path, matching every family's own prior
 * `form.quantity!` non-null assertion at the same point.
 */
export function demandCommonFieldsToPayload(
  f: DemandCommonEditFields | DemandCommonCreateFields,
): DemandCommonPayload {
  return {
    quantity: f.quantity as number,
    unit: f.unit.trim(),
    items_per_unit: f.items_per_unit,
    high_priority: f.high_priority,
    notify_on_delivery: f.notify_on_delivery,
    desired_delivery_date: formatDate(f.desired_delivery_date),
    note: f.note.trim() || null,
  }
}
