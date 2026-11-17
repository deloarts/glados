import type { DataImportProfile } from '../types/spreadsheetImport'

/**
 * The comparison form of a column name or header cell: trimmed, lower case,
 * inner whitespace collapsed. The backend normalises the configured names
 * the same way (data_import_profiles.normalize_column_name).
 */
export function normalizeColumnName(value: unknown): string {
  if (value === null || value === undefined) return ''
  return String(value).trim().replace(/\s+/g, ' ').toLowerCase()
}

/** The display form of a header cell: trimmed, inner whitespace collapsed. */
export function headerText(value: unknown): string {
  if (value === null || value === undefined) return ''
  const text = value instanceof Date ? value.toISOString().slice(0, 10) : String(value)
  return text.trim().replace(/\s+/g, ' ')
}

/** Normalised column name to the payload key of the field it maps to. */
export function columnNameIndex(profile: DataImportProfile): Map<string, string> {
  const index = new Map<string, string>()
  for (const field of profile.fields) {
    for (const name of field.column_names) {
      index.set(normalizeColumnName(name), field.key)
    }
  }
  return index
}
