import type { Content, ContentText, TableCell } from 'pdfmake/interfaces'

import { REPORT_COLORS, toneColors } from './palette'
import type { ReportTone } from './palette'
import { CONTENT_WIDTH, SPACING } from './styles'
import type { ReportStyle, Spacing } from './styles'

/**
 * The vocabulary of a report body: headings, text runs, tables, chips,
 * notices and figures. Builders compose reports from these only and never
 * write pdfmake layout or style values themselves, so every report shares
 * one look; the styles are named in utils/styles.ts and the page frame is
 * utils/reportDocument.ts.
 */

/** A run of inline text: plain, or an object in one of the named styles. */
export type Inline = string | ContentText

export interface KeyValue {
  label: Inline | Inline[]
  value: Inline | Inline[] | Content
}

export interface DataColumn {
  header: Inline | Inline[]
  /** A width in points, 'auto' or '*'. */
  width?: number | 'auto' | '*'
  align?: 'left' | 'right' | 'center'
}

/** What a table cell holds, with its look chosen by name. */
export interface CellOptions {
  style?: ReportStyle
  align?: 'left' | 'right' | 'center'
  noWrap?: boolean
  /** Sub-items sit one step in. */
  indent?: boolean
}

const INDENT = 12

// ── Inline text ──────────────────────────────────────────────────────────────

/** Text in one of the named styles, such as 'emphasis', 'muted' or 'note'. */
export function span(text: Inline | Inline[], style: ReportStyle): ContentText {
  return { text: Array.isArray(text) ? text : [text], style }
}

/** A formula symbol such as M with subscript max. */
export function symbol(base: string, sub: string): ContentText {
  return { text: [{ text: base, style: 'symbol' }, ...(sub ? [{ text: sub, sub: true }] : [])] }
}

/** A label followed by its formula symbol, "Max. torque Mmax". */
export function labelWithSymbol(label: string, base: string, sub: string): ContentText {
  if (!base) return { text: label }
  return { text: [`${label} `, symbol(base, sub)] }
}

/** A column header or label followed by its unit in a quieter style, "Mass kg". */
export function withUnit(label: string, unit: string): ContentText {
  return { text: [label, { text: ` ${unit}`, style: 'unit' }] }
}

/** A piece of formula text, set as a subscript or on the line. */
export interface FormulaPart {
  text: string
  sub: boolean
}

// A letter with a combining macron is a mean, x̄.
const MACRON = /(\p{L})\u0304/gu

function overlined(text: string): Inline[] {
  // The report fonts have no glyph for the macron, so the letter gets an overline.
  return text
    .split(MACRON)
    .map((piece, index): Inline => (index % 2 === 1 ? { text: piece, decoration: 'overline' } : piece))
    .filter((piece) => piece !== '')
}

/**
 * Formula text in the notation of standards, with real subscripts and
 * overlined means. The feature splits its notation into parts, since how a
 * subscript is written differs between tools.
 */
export function formula(parts: readonly FormulaPart[], style?: ReportStyle): ContentText {
  const text = parts.flatMap((part): Inline[] => (part.sub ? [{ text: part.text, sub: true }] : overlined(part.text)))
  return { text, ...(style ? { style } : {}) }
}

// ── Blocks ───────────────────────────────────────────────────────────────────

/** A paragraph, optionally in a named style and with space around it. */
export function paragraph(text: Inline | Inline[], style?: ReportStyle, spacing: Spacing = 'none'): Content {
  return { text: Array.isArray(text) ? text : [text], ...(style ? { style } : {}), margin: [...SPACING[spacing]] }
}

/** A small muted remark under a table or figure. */
export function footnote(text: Inline | Inline[]): Content {
  return { text: Array.isArray(text) ? text : [text], style: 'footnote' }
}

/** Blocks placed together with the given space around the group. */
export function group(blocks: readonly Content[], spacing: Spacing = 'none'): Content {
  return { stack: [...blocks], margin: [...SPACING[spacing]] }
}

/** Blocks that move to the next page together rather than being split. */
export function keepTogether(blocks: readonly Content[], spacing: Spacing = 'none'): Content {
  return { stack: [...blocks], unbreakable: true, margin: [...SPACING[spacing]] }
}

/** Two blocks side by side, each half the width. */
export function twoColumns(left: Content, right: Content): Content {
  return { columns: [{ stack: [left], width: '*' }, { stack: [right], width: '*' }], columnGap: 14 }
}

/** A block that starts on a new page. */
export function onNewPage(block: Content): Content {
  return { stack: [block], pageBreak: 'before' }
}

/** A section heading with a thin rule, kept on the page of what follows it. */
export function section(title: string, ...content: Content[]): Content {
  const [first, ...rest] = content
  return {
    stack: [
      {
        // The heading and the first block move to the next page together, so
        // a heading never ends a page on its own.
        stack: [
          { text: title, style: 'section' },
          {
            canvas: [
              { type: 'line', x1: 0, y1: 0, x2: CONTENT_WIDTH, y2: 0, lineWidth: 0.6, lineColor: REPORT_COLORS.rule },
            ],
            margin: [0, 2, 0, 6],
          },
          ...(first === undefined ? [] : [first]),
        ],
        unbreakable: true,
      },
      ...rest,
    ],
    margin: [0, 14, 0, 0],
  }
}

/** A sub-heading inside a section. */
export function subheading(text: Inline | Inline[]): Content {
  return { text: Array.isArray(text) ? text : [text], style: 'subheading' }
}

/** Label and value pairs in a grid of one or two pairs per row, on a light band. */
export function keyValueGrid(items: readonly KeyValue[], pairsPerRow: 1 | 2 = 2, spacing: Spacing = 'none'): Content {
  const asCell = (value: KeyValue['value'], style?: ReportStyle): TableCell =>
    typeof value === 'string' || Array.isArray(value) || 'text' in (value as object)
      ? { text: Array.isArray(value) ? value : [value as Inline], ...(style ? { style } : {}) }
      : (value as TableCell)
  const rows: TableCell[][] = []
  for (let i = 0; i < items.length; i += pairsPerRow) {
    const row: TableCell[] = []
    for (let j = 0; j < pairsPerRow; j++) {
      const item = items[i + j]
      row.push(item ? asCell(item.label, 'label') : '', item ? asCell(item.value) : '')
    }
    rows.push(row)
  }
  return {
    table: {
      widths: pairsPerRow === 2 ? ['auto', '*', 'auto', '*'] : ['auto', '*'],
      body: rows.length > 0 ? rows : [pairsPerRow === 2 ? ['', '', '', ''] : ['', '']],
    },
    layout: {
      fillColor: () => REPORT_COLORS.band,
      hLineWidth: () => 0,
      vLineWidth: () => 0,
      paddingLeft: (column) => (column % 2 === 0 ? 8 : 4),
      paddingRight: (column) => (column % 2 === 1 ? 12 : 4),
      paddingTop: (row) => (row === 0 ? 6 : 2),
      paddingBottom: (row, node) => (row === (node.table.body.length ?? 1) - 1 ? 6 : 2),
    },
    margin: [...SPACING[spacing]],
  }
}

/** A table cell of inline text, with its look chosen by name. */
export function cell(content: Inline | Inline[], options: CellOptions = {}): TableCell {
  return { text: Array.isArray(content) ? content : [content], ...cellOptions(options) } as TableCell
}

/** A table cell of blocks placed under each other, such as a value with a bar. */
export function blockCell(blocks: readonly Content[], options: CellOptions = {}): TableCell {
  return { stack: [...blocks], ...cellOptions(options) } as TableCell
}

/** A cell with a main line and smaller lines under it, such as a name and its note. */
export function noteCell(main: Inline | Inline[], notes: ReadonlyArray<Inline | Inline[]>, options: CellOptions = {}): TableCell {
  return blockCell(
    [{ text: Array.isArray(main) ? main : [main] }, ...notes.map((line) => paragraph(line, 'note'))],
    options,
  )
}

function cellOptions(options: CellOptions): object {
  return {
    ...(options.style ? { style: options.style } : {}),
    ...(options.align ? { alignment: options.align } : {}),
    ...(options.noWrap ? { noWrap: true } : {}),
    ...(options.indent ? { margin: [INDENT, 0, 0, 0] } : {}),
  }
}

/**
 * A data table with a header band repeated on every page, hairline rules
 * between rows and light zebra striping. `size` picks the text size for wide
 * tables.
 */
export function dataTable(
  columns: readonly DataColumn[],
  rows: readonly TableCell[][],
  size: 'normal' | 'small' | 'compact' = 'normal',
): Content {
  const header: TableCell[] = columns.map((column) => ({
    text: Array.isArray(column.header) ? column.header : [column.header],
    style: 'tableHeader',
    alignment: column.align ?? 'left',
  }))
  const body: TableCell[][] = rows.map((row) =>
    row.map((value, index) => {
      const align = columns[index]?.align
      if (!align || align === 'left') return value
      if (typeof value === 'string' || typeof value === 'number') return { text: String(value), alignment: align }
      return { alignment: align, ...(value as object) } as TableCell
    }),
  )
  const style: ReportStyle = size === 'compact' ? 'tableCompact' : size === 'small' ? 'tableSmall' : 'table'
  return {
    table: {
      headerRows: 1,
      dontBreakRows: true,
      widths: columns.map((column) => column.width ?? 'auto'),
      body: [header, ...body],
    },
    layout: {
      fillColor: (row) => (row === 0 ? REPORT_COLORS.band : row % 2 === 0 ? '#fafbfc' : null),
      hLineWidth: (row, node) => (row === 0 || row === node.table.body.length ? 0 : row === 1 ? 0.8 : 0.4),
      hLineColor: (row) => (row === 1 ? REPORT_COLORS.faint : REPORT_COLORS.rule),
      vLineWidth: () => 0,
      paddingLeft: () => 5,
      paddingRight: () => 5,
      paddingTop: () => 3,
      paddingBottom: () => 3,
    },
    style,
  }
}

/** A short status word on a tinted chip, for example "OK" or "Exceeded". */
export function statusChip(text: string, tone: ReportTone): Content {
  const colors = toneColors(tone)
  return {
    table: { body: [[{ text, color: colors.text, bold: true, fontSize: 8, noWrap: true }]] },
    layout: {
      fillColor: () => colors.fill,
      hLineWidth: () => 0,
      vLineWidth: () => 0,
      paddingLeft: () => 5,
      paddingRight: () => 5,
      paddingTop: () => 1,
      paddingBottom: () => 1,
    },
  }
}

/** A horizontal bar for a share between 0 and 1, capped at full width. */
export function shareBar(share: number, tone: ReportTone, width = 54): Content {
  const filled = Math.max(0, Math.min(1, share)) * width
  return {
    canvas: [
      { type: 'rect', x: 0, y: 0, w: width, h: 5, r: 2, color: REPORT_COLORS.band },
      ...(filled > 0 ? [{ type: 'rect' as const, x: 0, y: 0, w: filled, h: 5, r: 2, color: toneColors(tone).text }] : []),
    ],
    margin: [0, 3, 0, 0],
  }
}

/** A tinted box with a coloured edge, for a verdict, remarks or a warning. */
export function notice(content: Inline | Inline[] | Content, tone: ReportTone, title?: string): Content {
  const colors = toneColors(tone)
  const body: Content[] = []
  if (title) body.push({ text: title, bold: true, color: colors.text, margin: [0, 0, 0, 2] })
  body.push(
    typeof content === 'string' || Array.isArray(content) || 'text' in (content as object)
      ? { text: Array.isArray(content) ? content : [content as Inline] }
      : (content as Content),
  )
  return {
    table: { widths: ['*'], body: [[{ stack: body }]], dontBreakRows: true },
    layout: {
      fillColor: () => colors.fill,
      hLineWidth: () => 0,
      vLineWidth: (column) => (column === 0 ? 2.5 : 0),
      vLineColor: () => colors.text,
      paddingLeft: () => 8,
      paddingRight: () => 8,
      paddingTop: () => 5,
      paddingBottom: () => 5,
    },
    margin: [0, 4, 0, 4],
  }
}

/** One entry of a `list`, with the lists nested under it. */
export interface ListEntry {
  text: Inline | Inline[]
  sublists?: readonly ListBlock[]
}

/** A bulleted or numbered list whose entries may hold lists of their own. */
export interface ListBlock {
  ordered: boolean
  entries: readonly ListEntry[]
  /** The number of the first entry of a numbered list. */
  start?: number
}

/** A bulleted or numbered list, nested as deep as its entries go, such as written notes. */
export function list(block: ListBlock): Content {
  const items = block.entries.map((entry): Content => {
    const text = { text: Array.isArray(entry.text) ? entry.text : [entry.text] }
    const nested = (entry.sublists ?? []).map((sublist) => list(sublist))
    return nested.length > 0 ? { stack: [text, ...nested] } : text
  })
  const shared = { margin: [0, 2, 0, 0] as [number, number, number, number], markerColor: REPORT_COLORS.muted }
  return block.ordered
    ? { ol: items, ...(block.start !== undefined && block.start !== 1 ? { start: block.start } : {}), ...shared }
    : { ul: items, ...shared }
}

/** A bulleted list of plain sentences. */
export function bulletList(items: ReadonlyArray<Inline | Inline[]>): Content {
  return { ul: items.map((item) => ({ text: Array.isArray(item) ? item : [item] })), margin: [0, 2, 0, 0], markerColor: REPORT_COLORS.muted }
}

/** A figure from an SVG string, with a caption above it, kept on one page. */
export function svgFigure(caption: string, svg: string, width = CONTENT_WIDTH): Content {
  return {
    stack: [
      { text: caption, style: 'subheading' },
      { svg, width },
    ],
    unbreakable: true,
    margin: [0, 4, 0, 8],
  }
}

/** A drawing from an SVG string, centred, with an optional caption under it, kept on one page. */
export function drawing(svg: string, caption: string | null, width = 440): Content {
  return {
    stack: [{ svg, width, alignment: 'center' }, ...(caption ? [footnote(caption)] : [])],
    unbreakable: true,
    margin: [0, 4, 0, 10],
  }
}

/** A raster image from a data URL, fitted into a box of the given size. */
export function picture(dataUrl: string, fit: [number, number]): Content {
  return { image: dataUrl, fit }
}
