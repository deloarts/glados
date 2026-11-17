import { describe, it, expect } from 'vitest'

import {
  buildTableHtml,
  resolveOrderTemplate,
  DEFAULT_TABLE_COLUMNS,
  type TableColumnKey,
  type TableColumnLabels,
} from '../orderMailTemplate'
import type { OrderItemResponse } from '@/features/orders/types/ordersResponse'

// orderMailTemplate builds HTML that is later rendered via innerHTML/v-html
// (MailComposeDialog, SupplierOrderTemplateDialog); every case here guards
// against a user-controlled DB value (an item field, a template var) being
// interpreted as markup instead of text.

function itemWith(overrides: Partial<OrderItemResponse> = {}): OrderItemResponse {
  return {
    id: 1,
    status: 'pending',
    quantity: 2,
    items_per_unit: 1,
    unit: 'PCS',
    price: 400,
    note: null,
    item_order_code_1: 'CODE-1',
    item_article_name: 'Widget',
    project_number: 'PRJ-1',
    // Non-nullable on the wire even when the line type has no lot behind it,
    // so the fixture carries them rather than leaving them undefined.
    lot_number: '',
    fabrication_method: '',
    ...overrides,
  } as unknown as OrderItemResponse
}

const LABELS: TableColumnLabels = {
  row_no: '#',
  article_name: 'Article',
  part_number: 'Part No.',
  order_code_1: 'Code',
  order_code_2: 'Code 2',
  specification: 'Specification',
  material: 'Material',
  dimension: 'Dimension',
  item_type: 'Type',
  revision: 'Revision',
  base_size: 'Base Size',
  lot_number: 'Lot No.',
  fabrication_method: 'Fabrication Method',
  manufacturer: 'Manufacturer',
  mass: 'Mass [g]',
  quantity: 'Qty',
  items_per_unit: 'Per unit',
  unit: 'Unit',
  price: 'Price',
  note: 'Note',
  project: 'Project',
}

/** Cell texts of the single row buildTableHtml produced, in column order. */
function cellsOf(html: string): string[] {
  return [...html.matchAll(/<td[^>]*>(.*?)<\/td>/g)].map((m) => m[1]!)
}

describe('buildTableHtml', () => {
  it('escapes an <img onerror> payload in an item field instead of emitting a live tag', () => {
    const html = buildTableHtml(
      [itemWith({ item_article_name: '<img src=x onerror="alert(1)">' })],
      DEFAULT_TABLE_COLUMNS,
      LABELS,
    )

    // The payload survives only as inert escaped text: no live <img> tag,
    // so its onerror attribute never becomes a real DOM attribute.
    expect(html).not.toContain('<img')
    expect(html).toContain('&lt;img src=x onerror=&quot;alert(1)&quot;&gt;')
  })

  it('escapes a </td><td> cell-breakout payload rather than splitting the row', () => {
    const html = buildTableHtml(
      [itemWith({ item_article_name: '</td><td>INJECTED' })],
      DEFAULT_TABLE_COLUMNS,
      LABELS,
    )

    // Exactly one <td> per column (6 default columns); the payload did not
    // add an extra cell to the row.
    expect(html.match(/<td/g)).toHaveLength(DEFAULT_TABLE_COLUMNS.length)
    expect(html).toContain('&lt;/td&gt;&lt;td&gt;INJECTED')
  })

  it('escapes a <script> payload in a note field', () => {
    const html = buildTableHtml(
      [itemWith({ note: '<script>alert(document.cookie)</script>' })],
      ['note'] as TableColumnKey[],
      LABELS,
    )

    expect(html).not.toContain('<script>')
    expect(html).toContain('&lt;script&gt;alert(document.cookie)&lt;/script&gt;')
  })

  it('renders ordinary item data as a well-formed table', () => {
    const html = buildTableHtml(
      [itemWith({ item_article_name: 'Screw M4x12', quantity: 5, price: 250 })],
      ['article_name', 'quantity', 'price'] as TableColumnKey[],
      LABELS,
    )

    expect(html).toBe(
      '<table style="border-collapse:collapse;font-family:sans-serif;font-size:13px">' +
        '<thead><tr>' +
        '<th style="padding:4px 8px;border:1px solid #ccc;background:#f5f5f5;text-align:left">Article</th>' +
        '<th style="padding:4px 8px;border:1px solid #ccc;background:#f5f5f5;text-align:left">Qty</th>' +
        '<th style="padding:4px 8px;border:1px solid #ccc;background:#f5f5f5;text-align:left">Price</th>' +
        '</tr></thead><tbody><tr>' +
        '<td style="padding:4px 8px;border:1px solid #ccc">Screw M4x12</td>' +
        '<td style="padding:4px 8px;border:1px solid #ccc">5</td>' +
        '<td style="padding:4px 8px;border:1px solid #ccc">€2.50</td>' +
        '</tr></tbody></table>',
    )
  })
})

// A single order mixes line types, so a column that only one of them has must
// render blank on the others rather than leaking a neighbouring value.
describe('buildTableHtml - per-line-type columns', () => {
  const COLS = [
    'part_number',
    'revision',
    'material',
    'base_size',
    'lot_number',
    'fabrication_method',
  ] as TableColumnKey[]

  it('renders the manufacturing columns of a MADE line', () => {
    const html = buildTableHtml(
      [
        itemWith({
          line_type: 'MADE',
          item_order_code_1: '',
          item_article_name: 'Mounting Bracket',
          item_part_number: 'P-1042',
          item_revision: 'B',
          item_material: 'S235JR',
          item_base_size: '80x40x4',
          lot_number: 'LOT-0042',
          fabrication_method: 'Laser cutting, Bending',
        }),
      ],
      COLS,
      LABELS,
    )

    expect(cellsOf(html)).toEqual([
      'P-1042',
      'B',
      'S235JR',
      '80x40x4',
      'LOT-0042',
      'Laser cutting, Bending',
    ])
  })

  it('renders the raw-material columns of a SOURCE line', () => {
    const html = buildTableHtml(
      [
        itemWith({
          line_type: 'SOURCE',
          item_material: 'S355',
          item_dimension: '80x40x4',
          item_type_name: 'Flat bar',
          item_manufacturer: 'Steelco',
        }),
      ],
      ['material', 'dimension', 'item_type', 'manufacturer'] as TableColumnKey[],
      LABELS,
    )

    expect(cellsOf(html)).toEqual(['S355', '80x40x4', 'Flat bar', 'Steelco'])
  })

  it('leaves a column blank on a line type that has no such field', () => {
    // A BOUGHT line has no revision, material, base size, lot or fabrication
    // method; only its part number survives this column set.
    const html = buildTableHtml([itemWith({ item_part_number: 'PN-100234' })], COLS, LABELS)

    expect(cellsOf(html)).toEqual(['PN-100234', '', '', '', '', ''])
  })

  it('renders mass as plain grams, and blank rather than a placeholder when unset', () => {
    const html = buildTableHtml(
      [itemWith({ item_mass: 640 }), itemWith({ item_mass: null })],
      ['mass'] as TableColumnKey[],
      LABELS,
    )

    expect(cellsOf(html)).toEqual(['640', ''])
  })

  it('escapes an XSS payload carried in one of the new catalogue fields', () => {
    const html = buildTableHtml(
      [itemWith({ item_material: '<img src=x onerror="alert(1)">' })],
      ['material'] as TableColumnKey[],
      LABELS,
    )

    expect(html).not.toContain('<img')
    expect(html).toContain('&lt;img src=x onerror=&quot;alert(1)&quot;&gt;')
  })
})

describe('resolveOrderTemplate', () => {
  it('escapes an XSS payload carried in a template var (e.g. supplier note)', () => {
    const html = resolveOrderTemplate(
      '<p>Note: {{ note }}</p>',
      { note: '<img src=x onerror=alert(1)>' },
      [],
      LABELS,
    )

    expect(html).toBe('<p>Note: &lt;img src=x onerror=alert(1)&gt;</p>')
  })

  it('does not let a var value re-trigger table-token or var-token substitution', () => {
    // A var whose value happens to contain the literal text of another
    // token must render as inert text, not be interpreted a second time.
    const html = resolveOrderTemplate(
      '{{ note }}',
      { note: '{{ table }} {{ user_email }}' },
      [itemWith()],
      LABELS,
    )

    expect(html).toBe('{{ table }} {{ user_email }}')
    expect(html).not.toContain('<table')
  })

  it('substitutes the item table and leaves unknown vars as literal placeholders', () => {
    const html = resolveOrderTemplate(
      '<p>Hi {{ supplier }}</p>{{ table: article_name }}',
      { supplier: 'Acme & Co' },
      [itemWith({ item_article_name: 'Widget' })],
      LABELS,
    )

    expect(html).toContain('<p>Hi Acme &amp; Co</p>')
    expect(html).toContain('<table')
    expect(html).toContain('Widget')
  })
})

describe('buildTableHtml extra costs', () => {
  it('adds one escaped row per extra cost below the lines, across every column', () => {
    const html = buildTableHtml([itemWith()], DEFAULT_TABLE_COLUMNS, LABELS, undefined, [
      { name: 'Shipping', amount: '€15.00' },
      { name: '<b>Deposit</b>', amount: '€2.00' },
    ])

    expect(html).toContain(`colspan="${DEFAULT_TABLE_COLUMNS.length}">Shipping: €15.00</td>`)
    expect(html).toContain('&lt;b&gt;Deposit&lt;/b&gt;: €2.00')
    expect(html).not.toContain('<b>Deposit')
  })
})
