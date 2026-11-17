// The bought items adapter of the generic demand import.
import { BATCH_DEMAND_IMPORT_DRAFT_STORAGE_KEY } from '@/core/stores/resetOnLogout'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

import type { DemandImportAdapter, DemandImportFieldSpec } from '@/shared/demand-import'
import { formatUnit } from '@/shared/utils/units'
import { commitBatchDemands, validateBatchDemands, BoughtItemThumbnailCell } from '@/features/bought-items'
import type {
  BatchDemandRowInput,
  BatchDivergenceField,
  RowValidationResult,
  BoughtItemResponse,
} from '@/features/bought-items'

// Also the display order of the mapping and manual row UIs.
export type BoughtDemandField =
  | 'project'
  | 'quantity'
  | 'unit'
  | 'partNumber'
  | 'articleName'
  | 'orderCode'
  | 'manufacturerName'
  | 'desiredDeliveryDate'
  | 'note'

// Column names live in the import profile (Settings, Data import), keyed by payloadKey.
const FIELDS: DemandImportFieldSpec<BoughtDemandField>[] = [
  {
    key: 'project',
    alwaysRequired: true,
    kind: 'text',
    payloadKey: 'project_number',
  },
  {
    key: 'quantity',
    alwaysRequired: true,
    kind: 'number',
    payloadKey: 'quantity',
  },
  {
    key: 'unit',
    alwaysRequired: true,
    kind: 'text',
    payloadKey: 'unit',
  },
  {
    key: 'partNumber',
    kind: 'text',
    payloadKey: 'part_number',
  },
  {
    key: 'articleName',
    kind: 'text',
    payloadKey: 'article_name',
  },
  {
    key: 'orderCode',
    kind: 'text',
    payloadKey: 'order_code',
  },
  {
    key: 'manufacturerName',
    kind: 'text',
    payloadKey: 'manufacturer_name',
  },
  {
    key: 'desiredDeliveryDate',
    kind: 'date',
    payloadKey: 'desired_delivery_date',
  },
  {
    key: 'note',
    kind: 'text',
    payloadKey: 'note',
  },
]

// A row needs a part number, or order code plus manufacturer, to resolve to
// an item. The article name only feeds the divergence warning.
function hasLookupKey(partNumber: unknown, orderCode: unknown, manufacturerName: unknown): boolean {
  return !!partNumber || (!!orderCode && !!manufacturerName)
}

function isMappingComplete(mapping: Partial<Record<BoughtDemandField, string | null>>): boolean {
  const hasAlwaysRequired = FIELDS.filter((f) => f.alwaysRequired).every((f) => !!mapping[f.key])
  return hasAlwaysRequired && hasLookupKey(mapping.partNumber, mapping.orderCode, mapping.manufacturerName)
}

function isRowComplete(row: BatchDemandRowInput): boolean {
  const hasAlwaysRequired =
    !!row.project_number && row.quantity !== null && row.quantity > 0 && !!row.unit?.trim()
  return hasAlwaysRequired && hasLookupKey(row.part_number, row.order_code, row.manufacturer_name)
}

function buildRow(values: Record<BoughtDemandField, unknown>): BatchDemandRowInput {
  return {
    row_index: 0,
    project_number: (values.project as string | null) ?? null,
    quantity: (values.quantity as number | null) ?? null,
    unit: (values.unit as string | null) ?? null,
    part_number: (values.partNumber as string | null) ?? null,
    article_name: (values.articleName as string | null) ?? null,
    order_code: (values.orderCode as string | null) ?? null,
    manufacturer_name: (values.manufacturerName as string | null) ?? null,
    desired_delivery_date: (values.desiredDeliveryDate as string | null) ?? null,
    note: (values.note as string | null) ?? null,
  }
}

function catalogueArticleName(row: BatchDemandRowInput, result: RowValidationResult | undefined): string | null {
  if (!result || result.row_status !== 'matched') return null
  if (!result.divergences.some((d) => d.field === 'article_name')) return null
  return result.matched_item?.article_name ?? null
}

// Shows the catalogue part number for rows matched by order code.
function cataloguePartNumber(result: RowValidationResult | undefined): string | null {
  if (result?.match_source !== 'order_code_manufacturer') return null
  return result.matched_item?.part_number ?? null
}

function blockedHintKey(
  status: RowValidationResult['row_status'],
  _result: RowValidationResult | undefined,
): string | null {
  switch (status) {
    case 'not_found':
      return 'boughtItems.demands.batchCreate.errors.itemNotFound'
    case 'ambiguous':
      return 'boughtItems.demands.batchCreate.errors.ambiguous'
    case 'unresolved_reference':
      return 'boughtItems.demands.batchCreate.errors.projectNotFound'
    default:
      return null
  }
}

export const boughtItemsDemandImportAdapter: DemandImportAdapter<
  BoughtDemandField,
  BatchDemandRowInput,
  BoughtItemResponse,
  RowValidationResult
> = {
  id: 'bought-items',
  i18nPrefix: 'boughtItems.demands.batchCreate',
  importType: 'bought_item_demand',
  storageKey: BATCH_DEMAND_IMPORT_DRAFT_STORAGE_KEY,
  fields: FIELDS,
  isMappingComplete,
  isRowComplete,
  buildRow,
  validate: (rows) => validateBatchDemands({ rows }),
  commit: (rows) => commitBatchDemands({ rows }),
  reviewColumns: [
    {
      key: 'partNumber',
      headerKey: 'review.partNumber',
      width: '9rem',
      primary: (row) => row.part_number ?? getEmptyPlaceholder(),
      secondary: (_row, result) => cataloguePartNumber(result),
    },
    {
      key: 'item',
      headerKey: 'review.item',
      width: '18rem',
      primary: (row) => {
        const name = row.article_name ?? getEmptyPlaceholder()
        return row.order_code ? `${name}\n${row.order_code}` : name
      },
      secondary: (row, result) => catalogueArticleName(row, result),
    },
    {
      key: 'manufacturer',
      headerKey: 'review.manufacturer',
      width: '10rem',
      primary: (row) => row.manufacturer_name,
    },
  ],
  thumbnail: {
    component: BoughtItemThumbnailCell,
    itemId: (item) => item.id,
    itemName: (item) => item.article_name,
  },
  divergenceLabel: (field, t) =>
    t(`boughtItems.demands.batchCreate.divergenceField.${field as BatchDivergenceField}`),
  blockedHintKey,
  quantityUnit: (row) => formatUnit(row.unit),
}
