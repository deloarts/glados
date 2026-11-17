import type { ChartReference } from './chart'
import type {
  BrakeStop,
  Check,
  CheckKey,
  CheckStatus,
  DriveSizingSuccess,
  Issue,
  SegmentResult,
} from './engine'
import type { useDriveSizingFormat } from './format'
import { MAX_SEGMENTS, numericField } from './model'
import type { Orientation } from './model'
import type { Translate } from '@/core/i18n'

/**
 * Texts of the drive sizing results: the key figures, the rows of the checks
 * table, the verdict, the emergency stop, the phase of a segment and the
 * messages for errors and remarks. The tab and the PDF report both use them.
 */

type Format = ReturnType<typeof useDriveSizingFormat>

/** A formula symbol as base letter and subscript. */
export type FormulaSymbol = readonly [string, string]

export interface CheckRow {
  key: CheckKey
  name: string
  note: string
  value: string
  limit: string
  limitSymbol: FormulaSymbol | null
  utilisation: number | null
  utilisationText: string
  status: CheckStatus
  statusText: string
}

const LIMIT_SYMBOLS: Record<CheckKey, FormulaSymbol | null> = {
  peakTorque: ['M', 'max'],
  rmsTorque: ['M', 'N'],
  maxSpeed: ['n', 'max'],
  ratedSpeed: ['n', 'N'],
  axisTorque: ['M', 'axis'],
  stroke: null,
  brakeHolding: ['M', 'B'],
}

function amount(check: Check, value: number, fmt: Format): string {
  switch (check.key) {
    case 'maxSpeed':
    case 'ratedSpeed':
      return `${fmt.fixed(value, 0)} rpm`
    case 'stroke':
      return `${fmt.fixed(value, 0)} mm`
    default:
      return `${fmt.fixed(value, 2)} Nm`
  }
}

function checkNote(check: Check, brakeSafetyFactor: number, t: Translate, fmt: Format): string {
  const n = check.segment === undefined ? '' : check.segment + 1
  if (check.key === 'brakeHolding') {
    return t('tools.driveSizing.checks.notes.brakeHolding', { factor: fmt.num(brakeSafetyFactor, 2) })
  }
  return t(`tools.driveSizing.checks.notes.${check.key}`, { n })
}

export function checkRows(
  result: DriveSizingSuccess,
  options: { brakeSafetyFactor: number; maxSpeedGiven: boolean },
  t: Translate,
  fmt: Format,
): CheckRow[] {
  return result.checks.map((check) => {
    const value =
      check.key === 'stroke'
        ? `${fmt.fixed(result.minPositionMm, 0)} … ${fmt.fixed(result.maxPositionMm, 0)} mm`
        : amount(check, check.value, fmt)
    let limit: string
    if (check.limit !== null) limit = amount(check, check.limit, fmt)
    else if (check.key === 'brakeHolding') limit = t('tools.driveSizing.checks.noBrake')
    else limit = t('tools.driveSizing.checks.noLimit')
    // Without a separate maximum the rated speed is the limit of the speed check.
    const symbol =
      check.key === 'maxSpeed' && !options.maxSpeedGiven ? (['n', 'N'] as const) : LIMIT_SYMBOLS[check.key]
    return {
      key: check.key,
      name: t(`tools.driveSizing.checks.names.${check.key}`),
      note: checkNote(check, options.brakeSafetyFactor, t, fmt),
      value,
      limit,
      limitSymbol: check.limit === null ? null : symbol,
      utilisation: check.utilisation,
      utilisationText: check.utilisation === null ? '' : fmt.percent(check.utilisation),
      status: check.status,
      statusText: t(`tools.driveSizing.checks.status.${check.status}`),
    }
  })
}

/** "up, accelerating" or "standstill, brake holds". */
export function phaseLabel(segment: SegmentResult, orientation: Orientation, t: Translate): string {
  if (segment.phase === 'holdingBrake' || segment.phase === 'holdingMotor') {
    return t(`tools.driveSizing.segments.${segment.phase}`)
  }
  const horizontal = orientation === 'horizontal'
  const direction =
    segment.direction > 0 ? (horizontal ? 'forward' : 'up') : horizontal ? 'backward' : 'down'
  return t('tools.driveSizing.segments.phase', {
    direction: t(`tools.driveSizing.segments.direction.${direction}`),
    motion: t(`tools.driveSizing.segments.motion.${segment.phase}`),
  })
}

export function issueText(issue: Issue, t: Translate, fmt: Format, endPositionMm = 0): string {
  const field = issue.field === undefined ? null : numericField(issue.field)
  return t(`tools.driveSizing.issues.${issue.code}`, {
    field: field ? t(`tools.driveSizing.fields.${field.key}`) : '',
    group: field ? t(`tools.driveSizing.groups.${field.group}`) : '',
    n: issue.segment === undefined ? '' : issue.segment + 1,
    max: MAX_SEGMENTS,
    position: fmt.fixed(endPositionMm, 0),
  })
}

export type KeyFigureKey = 'cycleTime' | 'maxAxisSpeed' | 'radius' | 'inertia'

export function keyFigures(
  result: DriveSizingSuccess,
  fmt: Format,
): Array<{ key: KeyFigureKey; value: string }> {
  const maxAxisSpeed = Math.max(
    0,
    ...result.segments.map((segment) => Math.max(Math.abs(segment.startSpeed), Math.abs(segment.endSpeed))),
  )
  return [
    { key: 'cycleTime', value: `${fmt.fixed(result.cycleTimeS, 2)} s` },
    { key: 'maxAxisSpeed', value: `${fmt.fixed(maxAxisSpeed, 2)} m/s` },
    { key: 'radius', value: `${fmt.fixed(result.radiusM * 1000, 3)} mm` },
    { key: 'inertia', value: `${fmt.fixed(result.inertiaKgM2 * 1e4, 3)} kg·cm²` },
  ]
}

/** "All checks passed." or how many failed. */
export function verdictText(failed: number, t: Translate): string {
  if (failed === 0) return t('tools.driveSizing.checks.allPassed')
  if (failed === 1) return t('tools.driveSizing.checks.oneFailed')
  return t('tools.driveSizing.checks.manyFailed', { count: failed })
}

/** What the brake does in an emergency stop on the way down, or '' without one. */
export function brakeStopText(stop: BrakeStop | null, t: Translate, fmt: Format): string {
  if (!stop) return ''
  const common = { speed: fmt.fixed(stop.speedMs, 2), mass: fmt.num(stop.massKg, 2) }
  if (stop.decelerationMs2 === null || stop.distanceMm === null || stop.timeS === null) {
    return t('tools.driveSizing.brakeStop.cannotStop', common)
  }
  return t('tools.driveSizing.brakeStop.text', {
    ...common,
    deceleration: fmt.fixed(stop.decelerationMs2, 2),
    distance: fmt.fixed(stop.distanceMm, 1),
    time: fmt.fixed(stop.timeS, 3),
  })
}

/**
 * The lines across the torque chart: the RMS torque, and the motor's maximum
 * and rated torque only on the side the torque actually reaches, so a profile
 * that never needs a negative torque is not squeezed into half the chart.
 */
export function torqueReferences(
  result: DriveSizingSuccess,
  maxTorqueNm: number,
  ratedTorqueNm: number,
): ChartReference[] {
  const negative = result.segments.some((segment) => segment.torqueNm < 0)
  const positive = result.segments.some((segment) => segment.torqueNm > 0)
  const references: ChartReference[] = [{ value: result.rmsTorqueNm, symbol: ['M', 'rms'], tone: 'mean' }]
  if (positive || !negative) {
    references.push({ value: maxTorqueNm, symbol: ['M', 'max'], tone: 'limit' })
    references.push({ value: ratedTorqueNm, symbol: ['M', 'N'], tone: 'rated' })
  }
  if (negative) {
    references.push({ value: -maxTorqueNm, symbol: ['−M', 'max'], tone: 'limit' })
    references.push({ value: -ratedTorqueNm, symbol: ['−M', 'N'], tone: 'rated' })
  }
  return references
}
