import type { Style, StyleDictionary } from 'pdfmake/interfaces'

import { REPORT_COLORS, REPORT_FONTS } from './palette'

/**
 * Every text and cell style a report may use, by name. Builders refer to
 * these names only and never set sizes, colours or fonts themselves (a lint
 * rule enforces it), so all reports look the same and a design change is
 * made here once.
 */

/** Usable width between the side margins of an A4 page, in points. */
export const CONTENT_WIDTH = 515

// pdfmake also reads a cell's fill from its style, which its typings do not list.
type CellStyle = Style & { fillColor?: string }

const STYLES = {
  // The frame
  headerKind: { font: REPORT_FONTS.heading, fontSize: 12, bold: true, color: REPORT_COLORS.ink },
  headerDate: { fontSize: 9, color: REPORT_COLORS.muted },
  title: { font: REPORT_FONTS.heading, fontSize: 18, bold: true, color: REPORT_COLORS.ink },
  subtitle: { fontSize: 11, color: REPORT_COLORS.muted, margin: [0, 2, 0, 0] },
  footer: { fontSize: 8, color: REPORT_COLORS.muted },
  footerReference: { fontSize: 8, bold: true, color: REPORT_COLORS.ink },
  // Headings
  section: { font: REPORT_FONTS.heading, fontSize: 12, bold: true, color: REPORT_COLORS.ink },
  subheading: { font: REPORT_FONTS.heading, fontSize: 10, bold: true, color: REPORT_COLORS.ink, margin: [0, 6, 0, 3] },
  // Running text
  label: { fontSize: 8.5, color: REPORT_COLORS.muted },
  muted: { color: REPORT_COLORS.muted },
  faint: { color: REPORT_COLORS.faint },
  emphasis: { bold: true },
  italic: { italics: true },
  alert: { bold: true, color: REPORT_COLORS.fail },
  symbol: { italics: true },
  unit: { bold: false, color: REPORT_COLORS.muted },
  note: { fontSize: 7.5, color: REPORT_COLORS.muted },
  hint: { fontSize: 8, italics: true },
  footnote: { fontSize: 8, italics: true, color: REPORT_COLORS.muted, margin: [0, 3, 0, 0] },
  // A headline value, such as a safety distance, and its missing counterpart
  value: { fontSize: 20, bold: true, color: REPORT_COLORS.ink },
  valueMissing: { fontSize: 14, bold: true, color: REPORT_COLORS.fail },
  // Tables
  table: { fontSize: 8.5 },
  tableSmall: { fontSize: 8 },
  tableCompact: { fontSize: 7 },
  tableHeader: { bold: true, fontSize: 8.5, color: REPORT_COLORS.ink },
  cellMarked: { fillColor: REPORT_COLORS.accentSoft },
  cellMarkedHeader: { fillColor: REPORT_COLORS.accentSoft, bold: true },
  cellHit: { fillColor: REPORT_COLORS.accent, color: '#ffffff', bold: true },
} satisfies Record<string, CellStyle>

export type ReportStyle = keyof typeof STYLES

export const REPORT_STYLES: StyleDictionary = STYLES as StyleDictionary

/** Defaults of every text that names no style. */
export const DEFAULT_STYLE: Style = {
  font: REPORT_FONTS.body,
  fontSize: 9.5,
  color: REPORT_COLORS.ink,
  lineHeight: 1.15,
}

/** Vertical space around a block, in points: before and after. */
export const SPACING = {
  none: [0, 0, 0, 0],
  tight: [0, 2, 0, 2],
  before: [0, 6, 0, 0],
  normal: [0, 6, 0, 6],
  loose: [0, 10, 0, 10],
  after: [0, 0, 0, 8],
} as const satisfies Record<string, [number, number, number, number]>

export type Spacing = keyof typeof SPACING

/**
 * Colours for drawings a builder writes as SVG, such as charts, where a
 * named style cannot reach. Nothing else in a feature uses colour values.
 */
export const DRAWING_COLORS = {
  ink: REPORT_COLORS.ink,
  muted: REPORT_COLORS.muted,
  rule: REPORT_COLORS.rule,
  line: REPORT_COLORS.accent,
  limit: REPORT_COLORS.fail,
  rated: REPORT_COLORS.warn,
  font: REPORT_FONTS.body,
} as const
