// The made items adapter of the generic demand import. The only lookup key
// is part number plus revision, both required, so a row without a revision
// is invalid. Made item demands are always counted in PCS.
import { BATCH_MADE_ITEM_DEMAND_IMPORT_DRAFT_STORAGE_KEY } from '@/core/stores/resetOnLogout'

import type { DemandImportAdapter, DemandImportFieldSpec } from '@/shared/demand-import'
import {
  commitBatchMadeItemDemands,
  validateBatchMadeItemDemands,
  MadeItemThumbnailCell,
} from '@/features/made-items'
import type {
  MadeItemBatchDemandRowInput,
  MadeItemBatchDivergenceField,
  MadeItemRowValidationResult,
  MadeItemResponse,
} from '@/features/made-items'

// Also the display order of the mapping and manual row UIs.
export type MadeItemDemandField =
  | 'project'
  | 'quantity'
  | 'partNumber'
  | 'revision'
  | 'articleName'
  | 'desiredDeliveryDate'
  | 'note'

// Column names live in the import profile (Settings, Data import), keyed by payloadKey.
const FIELDS: DemandImportFieldSpec<MadeItemDemandField>[] = [
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
    key: 'partNumber',
    alwaysRequired: true,
    kind: 'text',
    payloadKey: 'part_number',
  },
  {
    key: 'revision',
    alwaysRequired: true,
    kind: 'text',
    payloadKey: 'revision',
  },
  {
    key: 'articleName',
    kind: 'text',
    payloadKey: 'article_name',
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

function isMappingComplete(mapping: Partial<Record<MadeItemDemandField, string | null>>): boolean {
  return FIELDS.filter((f) => f.alwaysRequired).every((f) => !!mapping[f.key])
}

function isRowComplete(row: MadeItemBatchDemandRowInput): boolean {
  return (
    !!row.project_number &&
    row.quantity !== null &&
    row.quantity > 0 &&
    !!row.part_number &&
    !!row.revision
  )
}

function buildRow(values: Record<MadeItemDemandField, unknown>): MadeItemBatchDemandRowInput {
  return {
    row_index: 0,
    project_number: (values.project as string | null) ?? null,
    quantity: (values.quantity as number | null) ?? null,
    part_number: (values.partNumber as string | null) ?? null,
    revision: (values.revision as string | null) ?? null,
    article_name: (values.articleName as string | null) ?? null,
    desired_delivery_date: (values.desiredDeliveryDate as string | null) ?? null,
    note: (values.note as string | null) ?? null,
  }
}

function partNumberPrimary(row: MadeItemBatchDemandRowInput): string | null {
  if (!row.part_number) return null
  return row.revision ? `${row.part_number}\nRev ${row.revision}` : row.part_number
}

function catalogueArticleName(
  result: MadeItemRowValidationResult | undefined,
): string | null {
  if (!result || result.row_status !== 'matched') return null
  if (!result.divergences.some((d) => d.field === 'article_name')) return null
  return result.matched_item?.article_name ?? null
}

function blockedHintKey(
  status: MadeItemRowValidationResult['row_status'],
  _result: MadeItemRowValidationResult | undefined,
): string | null {
  switch (status) {
    case 'not_found':
      return 'madeItems.demands.batchCreate.errors.itemNotFound'
    case 'ambiguous':
      return 'madeItems.demands.batchCreate.errors.ambiguous'
    case 'unresolved_reference':
      return 'madeItems.demands.batchCreate.errors.projectNotFound'
    default:
      return null
  }
}

export const madeItemsDemandImportAdapter: DemandImportAdapter<
  MadeItemDemandField,
  MadeItemBatchDemandRowInput,
  MadeItemResponse,
  MadeItemRowValidationResult
> = {
  id: 'made-items',
  i18nPrefix: 'madeItems.demands.batchCreate',
  importType: 'made_item_demand',
  storageKey: BATCH_MADE_ITEM_DEMAND_IMPORT_DRAFT_STORAGE_KEY,
  fields: FIELDS,
  isMappingComplete,
  isRowComplete,
  buildRow,
  validate: (rows) => validateBatchMadeItemDemands({ rows }),
  commit: (rows) => commitBatchMadeItemDemands({ rows }),
  reviewColumns: [
    {
      key: 'partNumber',
      headerKey: 'review.partNumber',
      width: '9rem',
      primary: partNumberPrimary,
    },
    {
      key: 'item',
      headerKey: 'review.item',
      width: '18rem',
      primary: (row) => row.article_name,
      secondary: (_row, result) => catalogueArticleName(result),
    },
  ],
  thumbnail: {
    component: MadeItemThumbnailCell,
    itemId: (item) => item.id,
    itemName: (item) => item.article_name,
  },
  divergenceLabel: (field, t) =>
    t(`madeItems.demands.batchCreate.divergenceField.${field as MadeItemBatchDivergenceField}`),
  // Shows the translated status label rather than the enum value.
  divergenceValue: (field, value, t) =>
    field === 'status' ? t(`madeItems.catalogue.status.${value}`) : value,
  blockedHintKey,
}
