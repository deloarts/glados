/**
 * The delivery tolerance fields of a bought or source item's edit form. An
 * item without its own value takes the one of the order settings, so an
 * empty field means "as in the settings".
 */
export const TOLERANCE_FIELDS = [
  'over_delivery_tolerance_percent',
  'under_delivery_tolerance_percent',
] as const

export type ToleranceField = (typeof TOLERANCE_FIELDS)[number]

export type ToleranceValues = Record<ToleranceField, number | null>

export const TOLERANCE_LABEL_KEYS: Record<ToleranceField, string> = {
  over_delivery_tolerance_percent: 'common.deliveryTolerance.over',
  under_delivery_tolerance_percent: 'common.deliveryTolerance.under',
}

/** The InputNumber props of a tolerance field: a percentage from 0 to 100. */
export const TOLERANCE_INPUT_PROPS = { min: 0, max: 100, maxFractionDigits: 2, suffix: ' %' }

export function emptyTolerances(): ToleranceValues {
  return { over_delivery_tolerance_percent: null, under_delivery_tolerance_percent: null }
}

export function tolerancesOf(item: Partial<ToleranceValues>, field: ToleranceField): number | null {
  return item[field] ?? null
}

/** The tolerances an update sends for one item: the form's where the user
 * edited them, else the item's own. */
export function tolerancesToSave(
  form: ToleranceValues,
  item: Partial<ToleranceValues>,
  edited: ReadonlySet<PropertyKey>,
): ToleranceValues {
  const saved = emptyTolerances()
  for (const field of TOLERANCE_FIELDS) {
    saved[field] = edited.has(field) ? form[field] : tolerancesOf(item, field)
  }
  return saved
}
