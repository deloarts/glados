// The fields of the bought-item batch create and how a mapped sheet row
// becomes the row the backend validates. Field order is the order of the
// mapping step and the row form. Without the Data Portal lookup a row needs
// its name, order code and manufacturer; with it, an order code or an
// EPLAN part number is enough, since the portal fills the rest.
import { hasRequiredColumns } from '@/shared/spreadsheet-import'

import type { ColumnMapping, ImportFieldSpec } from '@/shared/spreadsheet-import'
import type { BoughtItemImportRow } from '../types/boughtItemsImportTypes'

export type BoughtItemImportField =
  | 'articleName'
  | 'orderCode1'
  | 'manufacturerName'
  | 'edpPartNumber'
  | 'orderCode2'
  | 'gtin'
  | 'ean'
  | 'tariffNumber'
  | 'mass'
  | 'note'
  | 'weblink'
  | 'articleGroupNames'
  | 'productFamilyName'
  | 'partNumber'

export const BOUGHT_ITEM_IMPORT_FIELDS: ImportFieldSpec<BoughtItemImportField>[] = [
  { key: 'articleName', payloadKey: 'article_name', kind: 'text', alwaysRequired: true },
  { key: 'orderCode1', payloadKey: 'order_code_1', kind: 'text', alwaysRequired: true },
  { key: 'manufacturerName', payloadKey: 'manufacturer_name', kind: 'text', alwaysRequired: true },
  { key: 'edpPartNumber', payloadKey: 'edp_part_number', kind: 'text' },
  { key: 'orderCode2', payloadKey: 'order_code_2', kind: 'text' },
  { key: 'gtin', payloadKey: 'gtin', kind: 'text' },
  { key: 'ean', payloadKey: 'ean', kind: 'text' },
  { key: 'tariffNumber', payloadKey: 'tariff_number', kind: 'text' },
  { key: 'mass', payloadKey: 'mass', kind: 'number' },
  { key: 'note', payloadKey: 'note', kind: 'text' },
  { key: 'weblink', payloadKey: 'weblink', kind: 'text' },
  { key: 'articleGroupNames', payloadKey: 'article_group_names', kind: 'text' },
  { key: 'productFamilyName', payloadKey: 'product_family_name', kind: 'text' },
  { key: 'partNumber', payloadKey: 'part_number', kind: 'text' },
]

/**
 * The fields as one mode requires them. The EPLAN part number is only a
 * lookup key, so it is offered only with the lookup.
 */
export function importFieldsFor(lookup: boolean): ImportFieldSpec<BoughtItemImportField>[] {
  return lookup
    ? BOUGHT_ITEM_IMPORT_FIELDS.map((f) => ({ ...f, alwaysRequired: false }))
    : BOUGHT_ITEM_IMPORT_FIELDS.filter((f) => f.key !== 'edpPartNumber')
}

export function isImportMappingComplete(
  mapping: ColumnMapping<BoughtItemImportField>,
  lookup: boolean,
): boolean {
  if (lookup) return !!mapping.orderCode1 || !!mapping.edpPartNumber
  return hasRequiredColumns(mapping, BOUGHT_ITEM_IMPORT_FIELDS)
}

export function buildBoughtItemImportRow(
  values: Record<BoughtItemImportField, unknown>,
): BoughtItemImportRow {
  const text = (value: unknown) => (value as string | null | undefined) ?? null
  return {
    row_index: 0,
    article_name: text(values.articleName),
    order_code_1: text(values.orderCode1),
    manufacturer_name: text(values.manufacturerName),
    edp_part_number: text(values.edpPartNumber),
    order_code_2: text(values.orderCode2),
    gtin: text(values.gtin),
    ean: text(values.ean),
    tariff_number: text(values.tariffNumber),
    mass: (values.mass as number | null | undefined) ?? null,
    note: text(values.note),
    weblink: text(values.weblink),
    article_group_names: text(values.articleGroupNames),
    product_family_name: text(values.productFamilyName),
    part_number: text(values.partNumber),
    edp_part_id: null,
    skip_lookup: false,
  }
}
