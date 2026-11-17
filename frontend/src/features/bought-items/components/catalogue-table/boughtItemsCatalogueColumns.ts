import { TABLE_COL_WIDTH_ID, TABLE_COL_WIDTH_STATUS } from '@/core/constants/table'

// Fixed pixel/rem widths for the columns that need one; everything else
// falls back to an even 10% share of the table.
const FIXED_COLUMN_WIDTHS: Record<string, string> = {
  id: TABLE_COL_WIDTH_ID,
  status: TABLE_COL_WIDTH_STATUS,
  data_source: TABLE_COL_WIDTH_STATUS,
  pdf_files: '9rem',
}

export function columnWidth(field: string): string {
  return FIXED_COLUMN_WIDTHS[field] ?? '10%'
}

// The subset of BoughtItemResponse fields whose cell needs more than plain
// text: each one maps to its own small renderer component in
// catalogue-table rather than to plain text.
export const BOUGHT_ITEM_CUSTOM_BODY_FIELDS = new Set([
  'status',
  'article_groups',
  'product_family',
  'successor_item_id',
  'weblink',
  'pdf_files',
  'part_number',
  'created',
  'changed',
  'revision',
  'data_source',
])
