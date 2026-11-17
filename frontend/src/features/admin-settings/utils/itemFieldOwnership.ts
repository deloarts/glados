import type { ItemFieldOwnership, RevisionFieldPolicyEntry } from '../types/adminSettingsTypes'

export interface MapValidation {
  duplicate: boolean
  missingIdentity: boolean
}

// Variable names must be unique within a map, and part_number and revision
// must be mapped whenever another field is. Callers only offer mappable
// fields, so unknown field names cannot occur.
export function validateVariableMap(map: Record<string, string>): MapValidation {
  const mapped = Object.entries(map)
    .map(([field, value]) => [field, value.trim()] as const)
    .filter(([, value]) => value !== '')
  const values = mapped.map(([, value]) => value)
  const duplicate = new Set(values).size !== values.length
  // `kind` only routes by_kind folders and is not identity, so like the
  // backend it does not force part_number and revision to be mapped.
  const otherFieldsMapped = mapped.some(([field]) => field !== 'kind')
  const missingIdentity = otherFieldsMapped && (!map.part_number?.trim() || !map.revision?.trim())
  return { duplicate, missingIdentity }
}

/**
 * A by_kind folder reads `kind` from the made map only, so both maps must
 * name the same variable, or the bought entry would be silently ignored.
 * Returns true (blocking) when the entries differ, including one left blank.
 */
export function validateKindVariableMatch(
  madeMap: Record<string, string>,
  boughtMap: Record<string, string>,
): boolean {
  const made = (madeMap.kind ?? '').trim()
  const bought = (boughtMap.kind ?? '').trim()
  if (!made && !bought) return false
  return !made || !bought || made !== bought
}

/**
 * Datacard variables Glados writes into the vault after every sync and
 * ingest never reads.
 */
export const WRITEBACK_MAPPABLE_FIELDS = [
  'glados_ids',
  'newest_revision_sync_state',
  'newest_revision_synced_at',
] as const

/**
 * While write-back is enabled, each write-back field must map to the same
 * non-blank variable in both maps, since one datacard is written regardless
 * of the file's kind. Returns false (no error) when write-back is off.
 */
export function validateWritebackVariables(
  madeMap: Record<string, string>,
  boughtMap: Record<string, string>,
  writebackEnabled: boolean,
): boolean {
  if (!writebackEnabled) return false
  return WRITEBACK_MAPPABLE_FIELDS.some((field) => {
    const made = (madeMap[field] ?? '').trim()
    const bought = (boughtMap[field] ?? '').trim()
    return !made || !bought || made !== bought
  })
}

export function ownerSeverity(owner: ItemFieldOwnership['owner']): string {
  switch (owner) {
    case 'addin':
      return 'info'
    case 'pdm':
      return 'warn'
    case 'addin_web':
      return 'help'
    case 'web':
      return 'success'
    default:
      return 'secondary'
  }
}

/**
 * Flattens a required-field toggle map, holding field and pseudo-rule names,
 * into the checked names for one kind. Locked fields are never in the map.
 */
export function buildRequiredFieldNames(map: Record<string, boolean>): string[] {
  return Object.entries(map)
    .filter(([, checked]) => checked)
    .map(([name]) => name)
}

// revision_field_policy is edited from two tabs, each owning one column, so a
// save rebuilds the full array from the policy fields, the stored entries and
// this tab's column edits. Columns the caller does not own survive untouched,
// and a new policy field without a stored entry defaults both columns to false.
export function mergeRevisionFieldPolicy(
  policyFields: ItemFieldOwnership[],
  currentPolicy: RevisionFieldPolicyEntry[],
  localOverride: Record<string, boolean>,
  ownField: 'web_requires_revision' | 'pdm_update_in_place',
): RevisionFieldPolicyEntry[] {
  return policyFields.map((row) => {
    const existing = currentPolicy.find((entry) => entry.field === row.field)
    const base: RevisionFieldPolicyEntry = {
      field: row.field,
      web_requires_revision: existing?.web_requires_revision ?? false,
      pdm_update_in_place: existing?.pdm_update_in_place ?? false,
    }
    return { ...base, [ownField]: localOverride[row.field] ?? base[ownField] }
  })
}
