/**
 * Whether an item's field is currently locked by the PDM integration.
 *
 * `pdm_locked_fields` is computed server-side, the same rule the write path
 * enforces, and ships empty whenever the PDM integration is off or the item
 * is not PDM-owned. Lock state is nothing more than field-name membership in
 * that list. Both `BoughtItemResponse` and `MadeItemResponse` carry the field
 * with the same shape, so this works for either without importing either
 * feature's types.
 */
export function isPdmLocked(
  item: { pdm_locked_fields?: string[] } | null,
  field: string,
): boolean {
  return (item?.pdm_locked_fields ?? []).includes(field)
}
