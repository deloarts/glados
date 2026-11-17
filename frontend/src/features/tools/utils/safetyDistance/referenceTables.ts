import { ISO_13857_STRUCTURE_GAP, matchBeamRow, MAX_BOTTOM_EDGE, MAX_STRUCTURE_GAP } from './espe'
import { MINIMUM_GAPS } from './iso13854'
import { lookupOpening, OPENINGS_UPPER, REACH_OVER_STRUCTURE, REACH_OVER_STRUCTURE_LOW_RISK } from './iso13857'
import type { OpeningTable } from './iso13857'
import { openingTable } from './reach'
import {
  BEAM_HEIGHTS,
  BEAM_HEIGHTS_INDUSTRIAL,
  HINGE_ANGLES,
  HINGE_GUARD_WIDTHS,
  hingeGap,
  lookupByHazardHeight,
  lookupGrid,
  REACH_OVER_GRID,
  REACH_UNDER,
  REACH_UNDER_STRUCTURE,
  rowRead,
} from './tables'
import type { BeamPosition, BeamRow, HeightRow, ReachGrid } from './tables'
import { BODY_PARTS, OPENING_SHAPES } from './types'
import type { OpeningShape, SafetyDistanceInputs } from './types'
import type { Translate } from '@/core/i18n'

/**
 * The numeric tables the current mode reads, with the row and column the
 * calculation used marked: from ISO 13855:2024 Tables 2 to 4 for a light
 * curtain, Tables C.1 and C.2 for beams and Table 5 for a hinged guard; from
 * ISO 13857:2019 Tables 1 and 2 for reaching over a structure and Tables 4,
 * 5 and 7 for reaching through an opening; and Table 1 of ISO 13854:2017 for
 * a crushing point. The tab shows them under the calculation and the PDF
 * report in its appendix.
 */

export interface ReferenceRow {
  key: string
  label: string
  cells: string[]
}

export interface ReferenceTable {
  key: string
  title: string
  unit: string
  rowHeader: string
  columns: string[]
  rows: ReferenceRow[]
  activeRow: string | null
  activeColumn: number | null
  note: string
}

/**
 * The tables for `inputs`. `number` formats a table value with exactly
 * `digits` decimals in the caller's language.
 */
export function referenceTables(
  inputs: SafetyDistanceInputs,
  t: Translate,
  number: (value: number, digits: number) => string,
): ReferenceTable[] {
  const P = 'tools.safetyDistance.tables'

  function num(value: number, digits = 0): string {
    return number(value, digits)
  }

  /**
   * A reach grid read by hazard height and a height column, with the cell the
   * calculation read. Between two rows the one with the larger value is the
   * one read.
   */
  function gridTable(key: string, grid: ReachGrid, hazardHeight: number | null, columnValue: number | null): ReferenceTable {
    let activeRow: string | null = null
    let activeColumn: number | null = null
    if (hazardHeight !== null && columnValue !== null) {
      const lookup = lookupGrid(grid, hazardHeight, columnValue)
      if (lookup) {
        activeColumn = lookup.column
        const read = rowRead(grid, lookup)
        activeRow = read ? String(read.hazardHeight) : null
      }
    }
    return {
      key,
      title: t(`${P}.${key}.title`),
      unit: t(`${P}.${key}.unit`),
      rowHeader: t(`${P}.hazardHeight`),
      columns: grid.columns.map((edge) => num(edge)),
      rows: grid.rows.map((row) => ({
        key: String(row.hazardHeight),
        label: num(row.hazardHeight),
        cells: row.values.map((value) => num(value)),
      })),
      activeRow,
      activeColumn,
      note: t(`${P}.${key}.note`),
    }
  }

  /** Table 2 of ISO 13855 with the top edge of a light curtain, or the top beam of a multi-beam device. */
  function reachOverTable(): ReferenceTable {
    const e = inputs.espe
    if (e.device === 'multiBeam') {
      const heights = [...new Set(e.beamHeights)]
      const top = heights.length > 0 ? Math.max(...heights) : null
      return gridTable('reachOver', REACH_OVER_GRID, heights.length < 2 ? null : e.hazardHeight, top)
    }
    return gridTable('reachOver', REACH_OVER_GRID, e.structureAbove ? null : e.hazardHeight, e.topEdge)
  }

  function structureTable(): ReferenceTable {
    if (inputs.mode === 'structure') {
      const st = inputs.structure
      return st.lowRisk
        ? gridTable('structureLowRisk', REACH_OVER_STRUCTURE_LOW_RISK, st.hazardHeight, st.structureHeight)
        : gridTable('structure', REACH_OVER_STRUCTURE, st.hazardHeight, st.structureHeight)
    }
    return gridTable('structure', REACH_OVER_STRUCTURE, inputs.espe.hazardHeight, inputs.espe.structureTop)
  }

  const TABLE_KEYS: Record<string, string> = { '4': 'openings', '5': 'openingsChildren', '7': 'openingsLower' }

  /** An opening table of ISO 13857 with the row for e and the column for the shape. */
  function openingsTable(table: OpeningTable, shape: OpeningShape, e: number | null, slotLength: number | null): ReferenceTable {
    const key = TABLE_KEYS[table.table] ?? 'openings'
    const lower = table.table === '7'
    const lookup = e === null ? null : lookupOpening(table, shape, e, shape === 'slot' ? slotLength : null)
    const shapes: readonly OpeningShape[] = lower ? ['slot', 'square'] : OPENING_SHAPES
    const cell = (value: number | null) => (value === null ? t(`${P}.openings.notPermitted`) : `≥ ${num(value)}`)
    return {
      key,
      title: t(`${P}.${key}.title`),
      unit: t(`${P}.openings.unit`),
      rowHeader: t(`${P}.openings.size`),
      columns: [
        t(`${P}.openings.part`),
        ...shapes.map((s) => (lower && s === 'square' ? t(`${P}.openings.squareOrRound`) : t(`tools.safetyDistance.fields.shape.${s}`))),
      ],
      rows: table.rows.map((row, index) => {
        const previous = table.rows[index - 1]
        return {
          key: String(row.max),
          label: previous ? `${num(previous.max)} < e ≤ ${num(row.max)}` : `e ≤ ${num(row.max)}`,
          cells: [t(`tools.safetyDistance.parts.${row.part}`), ...shapes.map((s) => cell(row[s]))],
        }
      }),
      activeRow: lookup ? String(table.rows[lookup.row]?.max) : null,
      activeColumn: lookup ? 1 + Math.max(0, shapes.indexOf(lower && shape === 'round' ? 'square' : shape)) : null,
      note: t(`${P}.${key}.note`),
    }
  }

  function crushingTable(): ReferenceTable {
    const part = inputs.crushing.bodyPart
    return {
      key: 'crushing',
      title: t(`${P}.crushing.title`),
      unit: t(`${P}.crushing.unit`),
      rowHeader: t(`${P}.crushing.part`),
      columns: [t(`${P}.crushing.column`)],
      rows: BODY_PARTS.map((p) => ({ key: p, label: t(`tools.safetyDistance.fields.bodyPart.${p}`), cells: [num(MINIMUM_GAPS[p])] })),
      activeRow: part,
      activeColumn: part === null ? null : 0,
      note: t(`${P}.crushing.note`),
    }
  }

  /** The gap of a hinged guard or the known opening, as the guard calculation reads it. */
  function guardOpening(): { shape: OpeningShape; e: number | null } {
    const g = inputs.guard
    if (g.openingMethod === 'direct') return { shape: g.openingShape, e: g.opening }
    if (g.guardWidth === null || g.angle === null || g.guardThickness === null) return { shape: 'slot', e: null }
    return { shape: 'slot', e: Math.max(hingeGap(g.guardWidth, g.angle) - g.guardThickness, 0) }
  }

  function heightTable(key: string, table: readonly HeightRow[], active: number | null): ReferenceTable {
    return {
      key,
      title: t(`${P}.${key}.title`),
      unit: t(`${P}.${key}.unit`),
      rowHeader: t(`${P}.hazardHeight`),
      columns: [t(`${P}.${key}.column`)],
      rows: table.map((row) => ({ key: String(row.hazardHeight), label: num(row.hazardHeight), cells: [num(row.reach)] })),
      activeRow: active === null ? null : String(active),
      activeColumn: active === null ? null : 0,
      note: t(`${P}.rowDownNote`),
    }
  }

  function reachUnderTables(): ReferenceTable[] {
    const e = inputs.espe
    const hh = e.hazardHeight
    const tables: ReferenceTable[] = []
    let underRow: number | null = null
    if (!e.structureBelow && hh !== null && e.detection !== null && e.bottomEdge !== null) {
      if (e.bottomEdge <= MAX_BOTTOM_EDGE && e.detection + e.bottomEdge > 40) {
        underRow = lookupByHazardHeight(REACH_UNDER, hh).row
      }
    }
    tables.push(heightTable('reachUnder', REACH_UNDER, underRow))
    if (e.structureBelow) {
      const gap = e.structureGap
      const used = hh !== null && gap !== null && gap > ISO_13857_STRUCTURE_GAP && gap <= MAX_STRUCTURE_GAP
      tables.push(
        heightTable('reachUnderStructure', REACH_UNDER_STRUCTURE, used ? lookupByHazardHeight(REACH_UNDER_STRUCTURE, hh).row : null),
      )
    }
    return tables
  }

  function position(value: BeamPosition): string {
    if (value === 'halfWidth') return t(`${P}.beams.halfWidth`)
    if (value === 'halfDiameter') return t(`${P}.beams.halfDiameter`)
    return num(value)
  }

  function openingHeight(row: BeamRow): string {
    if (row.roundOpening) return t(`${P}.beams.round`, { min: num(row.roundOpening.min), max: num(row.roundOpening.max) })
    if (row.maxOpeningHeight !== undefined) return `≤ ${num(row.maxOpeningHeight)}`
    if (row.minOpeningHeight !== undefined) return `> ${num(row.minOpeningHeight)}`
    return t(`${P}.beams.any`)
  }

  function openingWidth(row: BeamRow): string {
    if (row.roundOpening) return '–'
    if (row.maxOpeningWidth !== undefined) return `≤ ${num(row.maxOpeningWidth)}`
    if (row.minOpeningWidth !== undefined) return `> ${num(row.minOpeningWidth)}`
    return t(`${P}.beams.any`)
  }

  function beamTables(): ReferenceTable[] {
    const e = inputs.espe
    const heights = e.device === 'multiBeam' ? [...new Set(e.beamHeights)].sort((a, b) => a - b) : []
    const match = matchBeamRow(heights)
    const columns = [
      ...[1, 2, 3, 4].map((n) => t(`${P}.beams.beam`, { n })),
      t(`${P}.beams.openingHeight`),
      t(`${P}.beams.openingWidth`),
    ]
    const table = (key: string, rows: readonly BeamRow[], number: 1 | 2): ReferenceTable => ({
      key,
      title: t(`${P}.${key}.title`),
      unit: t(`${P}.beams.unit`),
      rowHeader: t(`${P}.beams.count`),
      columns,
      rows: rows.map((row) => ({
        key: row.key,
        label: num(row.beams),
        cells: [0, 1, 2, 3].map((i) => {
          const value = row.positions[i]
          return value === undefined ? '–' : position(value)
        }).concat([openingHeight(row), openingWidth(row)]),
      })),
      activeRow: match && match.table === number ? match.row.key : null,
      activeColumn: null,
      note: t(`${P}.${key}.note`),
    })
    return [table('beamHeights', BEAM_HEIGHTS, 1), table('beamHeightsIndustrial', BEAM_HEIGHTS_INDUSTRIAL, 2)]
  }

  function hingeTable(): ReferenceTable {
    const g = inputs.guard
    const row = g.guardWidth !== null && (HINGE_GUARD_WIDTHS as readonly number[]).includes(g.guardWidth) ? String(g.guardWidth) : null
    const column = g.angle === null ? -1 : (HINGE_ANGLES as readonly number[]).indexOf(g.angle)
    return {
      key: 'hingeGap',
      title: t(`${P}.hingeGap.title`),
      unit: t(`${P}.hingeGap.unit`),
      rowHeader: t(`${P}.hingeGap.rowHeader`),
      columns: HINGE_ANGLES.map((angle) => `${num(angle)}°`),
      rows: HINGE_GUARD_WIDTHS.map((width) => ({
        key: String(width),
        label: num(width),
        cells: HINGE_ANGLES.map((angle) => num(hingeGap(width, angle), 1)),
      })),
      activeRow: row,
      activeColumn: column >= 0 ? column : null,
      note: t(`${P}.hingeGap.note`),
    }
  }

  /** H_GB as a slot, while ISO 13857 sets D_GU for it. */
  function underGap(): number | null {
    const gap = inputs.espe.structureGap
    return gap !== null && gap <= ISO_13857_STRUCTURE_GAP ? gap : null
  }

  switch (inputs.mode) {
    case 'espe': {
      const e = inputs.espe
      if (e.device === 'singleBeam') return beamTables()
      if (e.device === 'multiBeam') return [...beamTables(), reachOverTable()]
      const tables = [reachOverTable(), ...reachUnderTables()]
      if (e.structureAbove) tables.push(structureTable())
      if (e.structureBelow) tables.push(openingsTable(OPENINGS_UPPER, 'slot', underGap(), null))
      return tables
    }
    case 'guard': {
      const g = inputs.guard
      const opening = guardOpening()
      const table = openingsTable(OPENINGS_UPPER, opening.shape, opening.e, g.openingMethod === 'direct' ? g.slotLength : null)
      return g.openingMethod === 'hinged' ? [hingeTable(), table] : [table]
    }
    case 'structure':
      return [structureTable()]
    case 'opening': {
      const o = inputs.opening
      return [openingsTable(openingTable(o), o.shape, o.size, o.slotLength)]
    }
    case 'crushing':
      return [crushingTable()]
    default:
      return []
  }
}
