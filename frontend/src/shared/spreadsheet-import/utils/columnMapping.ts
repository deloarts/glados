import { normalizeColumnName } from './columnNames'

import type { ColumnMapping, DataImportProfile, ImportFieldSpec } from '../types/spreadsheetImport'

/**
 * Maps each field to a header by the column names of the import profile. A
 * field maps only when exactly one unused header carries one of its names;
 * two candidates are ambiguous and left for the user rather than guessed.
 */
export function autoMapColumns<K extends string>(
  headers: string[],
  fields: ImportFieldSpec<K>[],
  profile: DataImportProfile,
): ColumnMapping<K> {
  const namesByField = new Map(
    profile.fields.map((f) => [f.key, new Set(f.column_names.map(normalizeColumnName))]),
  )
  const usedHeaders = new Set<string>()
  const mapping = {} as ColumnMapping<K>

  for (const field of fields) {
    const names = namesByField.get(field.payloadKey) ?? new Set<string>()
    const candidates = headers.filter(
      (h) => !usedHeaders.has(h) && names.has(normalizeColumnName(h)),
    )
    if (candidates.length === 1) {
      mapping[field.key] = candidates[0]!
      usedHeaders.add(candidates[0]!)
    } else {
      mapping[field.key] = null
    }
  }

  return mapping
}

/** True when every always-required field has a column. */
export function hasRequiredColumns<K extends string>(
  mapping: ColumnMapping<K>,
  fields: ImportFieldSpec<K>[],
): boolean {
  return fields.filter((f) => f.alwaysRequired).every((f) => !!mapping[f.key])
}

export function toNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null
  const n = typeof value === 'number' ? value : Number(String(value).trim().replace(',', '.'))
  return Number.isFinite(n) ? n : null
}

export function toText(value: unknown): string | null {
  if (value === null || value === undefined) return null
  const text = value instanceof Date ? value.toISOString().slice(0, 10) : String(value).trim()
  return text.length > 0 ? text : null
}

// A Date cell is read in the calendar of the browser that parsed it, so its
// local date is used rather than the UTC one, which can be a day earlier.
function localIsoDate(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function toDateString(value: unknown): string | null {
  if (value === null || value === undefined || value === '') return null
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : localIsoDate(value)
  }
  const date = new Date(String(value))
  return Number.isNaN(date.getTime()) ? null : date.toISOString().slice(0, 10)
}

function coerce(value: unknown, kind: ImportFieldSpec<string>['kind']): unknown {
  switch (kind) {
    case 'number':
      return toNumber(value)
    case 'date':
      return toDateString(value)
    default:
      return toText(value)
  }
}

/**
 * Coerces each sheet row's mapped cells by their field's `kind` and hands
 * the resulting {fieldKey: value} bag to the import's own buildRow(), the
 * one place where the import shapes its payload row.
 */
export function buildRowsFromMapping<K extends string, TRow>(
  rawRows: Record<string, unknown>[],
  mapping: ColumnMapping<K>,
  spec: { fields: ImportFieldSpec<K>[]; buildRow(values: Record<K, unknown>): TRow },
): TRow[] {
  return rawRows.map((raw) => {
    const values = {} as Record<K, unknown>
    for (const field of spec.fields) {
      const header = mapping[field.key]
      values[field.key] = coerce(header ? raw[header] : null, field.kind)
    }
    return spec.buildRow(values)
  })
}
