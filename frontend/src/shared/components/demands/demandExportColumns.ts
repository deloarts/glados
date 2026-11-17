import { dateCell, recordLinkCell, type SpreadsheetColumn } from '@/shared/spreadsheet-export'
import { formatUnit } from '@/shared/utils/units'

import type { PublicUser } from '@/core/types/userResponse'

/** The fields every demand list response carries, which the shared columns read. */
// eslint-disable-next-line no-restricted-syntax -- a structural type the three demand responses satisfy
export interface DemandExportRow {
  id: number
  status: string
  bucket_id: number | null
  quantity: number
  unit: string
  project_number: string
  project_customer: string
  project_description: string
  high_priority: boolean
  desired_delivery_date?: string | null
  created: string
  creator: PublicUser | null
  note: string | null
}

export interface DemandExportColumnsOptions<TRow extends DemandExportRow> {
  t: (key: string) => string
  /** The kind's i18n prefix, such as `boughtItems.demands`, for its headers and status labels. */
  prefix: string
  /** The name of a bucket, from the buckets store of the kind. */
  bucketName: (bucketId: number) => string | null
  /** The columns that describe the demanded item, which differ per kind. */
  itemColumns: SpreadsheetColumn<TRow>[]
  /** The public id of the demanded item, whose page the last column links. */
  itemPublicId: (row: TRow) => string | null | undefined
  /** False for a kind whose table has no priority column. */
  priority?: boolean
}

/**
 * The export columns of a demand list, the same for every item kind: the
 * demand's number, stored status, bucket, quantity and unit, its project,
 * then the kind's item columns, the priority where the kind's table shows
 * one, the desired delivery, when and by whom it was created, its note and
 * last the link to the demanded item, since a demand has no page of its own. The status is the one the demand
 * stores. The table refines it with the allocations, which the export does
 * not read.
 */
export function demandExportColumns<TRow extends DemandExportRow>(
  options: DemandExportColumnsOptions<TRow>,
): SpreadsheetColumn<TRow>[] {
  const { t, prefix } = options
  return [
    { header: t(`${prefix}.columns.id`), value: (row) => row.id },
    { header: t(`${prefix}.columns.status`), value: (row) => t(`${prefix}.status.${row.status}`) },
    {
      header: t(`${prefix}.buckets.column`),
      value: (row) => (row.bucket_id === null ? null : options.bucketName(row.bucket_id)),
    },
    { header: t(`${prefix}.columns.quantity`), value: (row) => row.quantity },
    { header: t('spreadsheetExport.columns.unit'), value: (row) => formatUnit(row.unit) || null },
    { header: t(`${prefix}.columns.project`), value: (row) => row.project_number || null },
    { header: t('spreadsheetExport.columns.customer'), value: (row) => row.project_customer || null },
    {
      header: t('spreadsheetExport.columns.projectDescription'),
      value: (row) => row.project_description || null,
    },
    ...options.itemColumns,
    ...(options.priority === false
      ? []
      : [
          {
            header: t(`${prefix}.columns.highPriority`),
            value: (row: TRow) => (row.high_priority ? t('common.yes') : t('common.no')),
          },
        ]),
    { header: t(`${prefix}.columns.desiredDelivery`), value: (row) => dateCell(row.desired_delivery_date) },
    { header: t(`${prefix}.columns.created`), value: (row) => dateCell(row.created) },
    { header: t('spreadsheetExport.columns.createdBy'), value: (row) => row.creator?.full_name ?? null },
    { header: t('spreadsheetExport.columns.note'), value: (row) => row.note || null },
    {
      header: t('spreadsheetExport.columns.itemLink'),
      value: (row) => {
        const publicId = options.itemPublicId(row)
        return publicId ? recordLinkCell(publicId) : null
      },
    },
  ]
}
