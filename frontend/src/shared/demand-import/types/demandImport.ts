// Types shared by every demand-import adapter. Nothing in shared/demand-import
// may import from features.
import type { Component } from 'vue'

import type { Schemas } from '@/core/api/generated'
import type { DataImportType, ImportFieldSpec } from '@/shared/spreadsheet-import'

export type ImportRowStatus = 'matched' | 'not_found' | 'ambiguous' | 'unresolved_reference' | 'invalid'

export interface ImportDivergence<F extends string = string> {
  field: F
  db_value: string | null
  file_value: string | null
}

// eslint-disable-next-line no-restricted-syntax -- generic over the item kind; each kind's generated validation response must satisfy it
export interface ImportRowValidation<TItem, F extends string = string, S extends string = string> {
  row_index: number
  row_status: ImportRowStatus
  match_source: S | null
  matched_item: TItem | null
  divergences: ImportDivergence<F>[]
  resolved_project_id: number | null
  errors: string[]
}

// eslint-disable-next-line no-restricted-syntax -- generic over the row result; each kind's generated validation response must satisfy it
export interface ImportValidateResponse<R> {
  results: R[]
  all_valid: boolean
}

/** The bought and made item commit responses share this shape. */
export type ImportCommitResponse = Schemas['CommitBatchDemandsResponse']

export type ImportStep = 'upload' | 'mapColumns' | 'review'

export interface DraftRow<TRow> {
  clientId: string
  data: TRow
}

/**
 * The fields every adapter row carries: project and quantity, which the
 * shared review table renders itself, and row_index, the backend's row
 * correlation id.
 */
export interface DemandImportRow {
  row_index: number
  project_number: string | null
  quantity: number | null
}

/**
 * One column-mapping field of a demand import: display order in the
 * mapping-step UI (array order), the payload key on TRow, which also keys
 * the field's column names in the import profile, and how to coerce a raw
 * cell value (kind).
 */
export type DemandImportFieldSpec<K extends string> = ImportFieldSpec<K>

export interface ReviewColumnSpec<TRow, R> {
  key: string
  /** i18n key under the adapter's own i18nPrefix, or already fully-qualified with it. */
  headerKey: string
  width?: string
  primary(row: TRow): string | null
  /** Muted line under primary, for example the catalogue value when it diverges from the file. */
  secondary?(row: TRow, result: R | undefined): string | null
}

/**
 * What a kind plugs in to get the whole upload, mapping, review, validate and
 * commit flow (see boughtItemsDemandImportAdapter.ts).
 */
export interface DemandImportAdapter<
  K extends string,
  TRow extends DemandImportRow,
  TItem,
  R extends ImportRowValidation<TItem> = ImportRowValidation<TItem>,
> {
  /** 'bought-items' | 'made-items'; also used to namespace the draft store id. */
  id: string
  /** The import profile (header row, row limit, column names) this import reads. */
  importType: DataImportType
  /** e.g. 'boughtItems.demands.batchCreate'; every UI string is looked up under this prefix. */
  i18nPrefix: string
  storageKey: string
  /** Display order = mapping-step UI order. */
  fields: DemandImportFieldSpec<K>[]
  isMappingComplete(mapping: Partial<Record<K, string | null>>): boolean
  /** Gates the manual "Add Row" form's submit button. */
  isRowComplete(row: TRow): boolean
  /** Builds a full TRow from coerced cell/form values (no row_index; the store assigns it). */
  buildRow(values: Record<K, unknown>): TRow
  validate(rows: TRow[]): Promise<ImportValidateResponse<R>>
  commit(rows: TRow[]): Promise<ImportCommitResponse>
  /** The kind-specific middle columns rendered between Quantity and Details. */
  reviewColumns: ReviewColumnSpec<TRow, R>[]
  thumbnail?: {
    component: Component
    itemId(item: TItem): number
    itemName(item: TItem): string
  }
  /** A translated divergence-field label, e.g. (field, t) => t(`${prefix}.divergenceField.${field}`). */
  divergenceLabel(field: string, t: (key: string) => string): string
  /**
   * Optional display formatting for a divergence's file/db value, for example to
   * translate an enum value such as a catalogue status. Return the value
   * unchanged for fields that need no formatting.
   */
  divergenceValue?(field: string, value: string, t: (key: string) => string): string
  /** Absolute i18n key for the hint shown under a blocked row's error text, or null for none. */
  blockedHintKey(status: ImportRowStatus, result: R | undefined): string | null
  /** Unit suffix shown after the Quantity column's number: bought shows it, made shows nothing. */
  quantityUnit?(row: TRow): string | null
}
