import type { Schemas } from '@/core/api/generated'
import type { AppLocale } from '@/core/i18n'
import { formatPrice } from '@/core/utils/currency'
import { formatDecimal } from '@/core/utils/numbers'
import { formatUnit } from '@/shared/utils/units'

// ── Column definitions ────────────────────────────────────────────────────────

// One order mixes bought, made, source and virtual lines, so cellValue()
// returns '' for a field a line type does not have.
export const TABLE_COLUMN_KEYS = [
  'row_no',
  'article_name',
  'part_number',
  'order_code_1',
  'order_code_2',
  'specification',
  'material',
  'dimension',
  'item_type',
  'revision',
  'base_size',
  'lot_number',
  'fabrication_method',
  'manufacturer',
  'mass',
  'quantity',
  'items_per_unit',
  'unit',
  'price',
  'note',
  'project',
] as const

export type TableColumnKey = (typeof TABLE_COLUMN_KEYS)[number]

export const DEFAULT_TABLE_COLUMNS: TableColumnKey[] = [
  'row_no',
  'article_name',
  'order_code_1',
  'quantity',
  'unit',
  'price',
]

export type TableColumnLabels = Record<TableColumnKey, string>

/**
 * What a mail table reads from a row: an order line, or a quote request
 * line shaped like one, whose missing fields stay blank.
 */
export type MailTableItem = Pick<
  Schemas['OrderItemResponse'],
  | 'item_article_name'
  | 'item_part_number'
  | 'item_order_code_1'
  | 'item_order_code_2'
  | 'item_specification'
  | 'item_material'
  | 'item_dimension'
  | 'item_type_name'
  | 'item_revision'
  | 'item_base_size'
  | 'lot_number'
  | 'fabrication_method'
  | 'item_manufacturer'
  | 'item_mass'
  | 'quantity'
  | 'items_per_unit'
  | 'unit'
  | 'price'
  | 'note'
  | 'project_number'
>

function cellValue(
  col: TableColumnKey,
  item: MailTableItem,
  index: number,
  unitLocale?: AppLocale,
): string {
  switch (col) {
    case 'row_no':
      return String(index + 1)
    case 'article_name':
      return item.item_article_name
    case 'part_number':
      return item.item_part_number ?? ''
    case 'order_code_1':
      return item.item_order_code_1
    case 'order_code_2':
      return item.item_order_code_2 ?? ''
    case 'specification':
      return item.item_specification
    case 'material':
      return item.item_material ?? ''
    case 'dimension':
      return item.item_dimension ?? ''
    case 'item_type':
      return item.item_type_name ?? ''
    case 'revision':
      return item.item_revision ?? ''
    case 'base_size':
      return item.item_base_size ?? ''
    case 'lot_number':
      return item.lot_number
    case 'fabrication_method':
      return item.fabrication_method
    case 'manufacturer':
      return item.item_manufacturer ?? ''
    case 'mass':
      // Blank rather than the UI placeholder, since this lands in a supplier mail.
      return formatDecimal(item.item_mass, '')
    case 'quantity':
      return String(item.quantity)
    case 'items_per_unit':
      return String(item.items_per_unit)
    case 'unit':
      return formatUnit(item.unit, unitLocale)
    case 'price':
      return formatPrice(item.price, unitLocale)
    case 'note':
      return item.note ?? ''
    case 'project':
      return item.project_number
    default:
      return ''
  }
}

// ── HTML escaping ─────────────────────────────────────────────────────────────

// Every interpolated value must be escaped: item fields and vars are
// user-controlled and the HTML is rendered for other users. The template
// markup itself stays unescaped and is sanitized at the render sinks.
function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

// ── HTML table builder ────────────────────────────────────────────────────────

const TH = 'padding:4px 8px;border:1px solid #ccc;background:#f5f5f5;text-align:left'
const TD = 'padding:4px 8px;border:1px solid #ccc'
const TABLE = 'border-collapse:collapse;font-family:sans-serif;font-size:13px'

/** An extra cost as a mail table shows it below the lines, already formatted. */
export interface MailTableExtra {
  name: string
  amount: string
}

export function buildTableHtml(
  items: MailTableItem[],
  cols: TableColumnKey[],
  labels: TableColumnLabels,
  unitLocale?: AppLocale,
  extras: MailTableExtra[] = [],
): string {
  const ths = cols.map((c) => `<th style="${TH}">${escapeHtml(labels[c])}</th>`).join('')
  const rows = items
    .map((item, i) => {
      const tds = cols
        .map((c) => `<td style="${TD}">${escapeHtml(cellValue(c, item, i, unitLocale))}</td>`)
        .join('')
      return `<tr>${tds}</tr>`
    })
    .join('')
  // Extra costs have no line columns, so each takes one row across them.
  const extraRows = extras
    .map(
      (extra) =>
        `<tr><td style="${TD}" colspan="${cols.length}">` +
        `${escapeHtml(extra.name)}: ${escapeHtml(extra.amount)}</td></tr>`,
    )
    .join('')
  return (
    `<table style="${TABLE}"><thead><tr>${ths}</tr></thead>` +
    `<tbody>${rows}${extraRows}</tbody></table>`
  )
}

// ── Template resolution ───────────────────────────────────────────────────────

// Shared with the preview, so sending and previewing parse the same token.
export const TABLE_TOKEN_RE = /\{\{\s*table(?:\s*:\s*([^}]*?))?\s*\}\}/g

export function parseCols(colList: string | undefined): TableColumnKey[] {
  if (!colList) return DEFAULT_TABLE_COLUMNS
  const parsed = colList
    .split(',')
    .map((c) => c.trim())
    .filter((c): c is TableColumnKey => TABLE_COLUMN_KEYS.includes(c as TableColumnKey))
  return parsed.length > 0 ? parsed : DEFAULT_TABLE_COLUMNS
}

/** Resolves template to an HTML string (for EML / preview). */
export function resolveOrderTemplate(
  template: string,
  vars: Record<string, string>,
  items: MailTableItem[],
  labels: TableColumnLabels,
  unitLocale?: AppLocale,
  extras: MailTableExtra[] = [],
): string {
  const withTable = template.replace(TABLE_TOKEN_RE, (_, colList?: string) =>
    buildTableHtml(items, parseCols(colList), labels, unitLocale, extras),
  )
  return withTable.replace(/\{\{\s*(\w+)\s*\}\}/g, (_, key: string) => {
    const value = vars[key]
    return value !== undefined ? escapeHtml(value) : `{{ ${key} }}`
  })
}
