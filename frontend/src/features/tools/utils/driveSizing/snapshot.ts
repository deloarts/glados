import type { CheckKey, DriveSizingResult, Issue } from './engine'
import { withoutNegativeZero } from '@/core/utils/numbers'
import type { DriveSizingInput } from './model'

/**
 * The results a saved drive sizing keeps. Numbers are rounded to what the
 * tab shows plus a digit, keys stay the same across versions of the engine,
 * and `setup` repeats the few inputs a one-line summary needs, since the
 * summary only ever sees the results.
 */

// Math.round on the scaled value, not `roundTo`: the two disagree on some
// halves, and changing the rounding would mark stored snapshots as drifted.
function round(value: number, digits: number): number {
  const factor = 10 ** digits
  return withoutNegativeZero(Math.round(value * factor) / factor)
}

const CHECK_DIGITS: Record<CheckKey, number> = {
  peakTorque: 3,
  rmsTorque: 3,
  maxSpeed: 1,
  ratedSpeed: 1,
  axisTorque: 3,
  stroke: 1,
  brakeHolding: 3,
}

function issueSnapshot(issue: Issue): Record<string, unknown> {
  return {
    code: issue.code,
    ...(issue.field === undefined ? {} : { field: issue.field }),
    ...(issue.segment === undefined ? {} : { segment: issue.segment }),
  }
}

export function driveSizingSnapshot(
  input: DriveSizingInput,
  result: DriveSizingResult,
): Record<string, unknown> {
  const setup = {
    orientation: input.orientation,
    angleDeg: input.orientation === 'inclined' ? input.angleDeg : null,
    transmission: input.transmission,
    ratio: input.ratio,
    carriageMassKg: input.carriageMassKg,
    payloadMassKg: input.payloadMassKg,
  }
  if (!result.ok) return { setup, ok: false, errors: result.errors.map(issueSnapshot) }

  const checks: Record<string, unknown> = {}
  for (const check of result.checks) {
    const digits = CHECK_DIGITS[check.key]
    checks[check.key] = {
      value: round(check.value, digits),
      limit: check.limit === null ? null : round(check.limit, digits),
      utilisationPct: check.utilisation === null ? null : round(check.utilisation * 100, 1),
      status: check.status,
      segment: check.segment ?? null,
    }
  }
  const stop = result.brakeStop

  return {
    setup,
    ok: true,
    radiusMm: round(result.radiusM * 1000, 3),
    inertiaKgCm2: round(result.inertiaKgM2 * 1e4, 3),
    cycleTimeS: round(result.cycleTimeS, 3),
    peakTorqueNm: round(result.peakTorqueNm, 3),
    rmsTorqueNm: round(result.rmsTorqueNm, 3),
    maxSpeedRpm: round(result.maxSpeedRpm, 1),
    positionMm: {
      min: round(result.minPositionMm, 1),
      max: round(result.maxPositionMm, 1),
      end: round(result.endPositionMm, 1),
    },
    checks,
    failedChecks: result.checks.filter((check) => check.status === 'fail').length,
    brakeStop: stop
      ? {
          speedMs: round(stop.speedMs, 3),
          massKg: round(stop.massKg, 2),
          decelerationMs2: stop.decelerationMs2 === null ? null : round(stop.decelerationMs2, 3),
          distanceMm: stop.distanceMm === null ? null : round(stop.distanceMm, 1),
          timeS: stop.timeS === null ? null : round(stop.timeS, 3),
        }
      : null,
    warnings: result.warnings.map(issueSnapshot),
    segments: result.segments.map((segment) => ({
      index: segment.index,
      kind: segment.kind,
      phase: segment.phase,
      direction: segment.direction,
      payload: segment.payload,
      massKg: round(segment.massKg, 2),
      startMm: round(segment.startMm, 1),
      endMm: round(segment.endMm, 1),
      startTimeS: round(segment.startTimeS, 3),
      durationS: round(segment.durationS, 3),
      startSpeed: round(segment.startSpeed, 3),
      endSpeed: round(segment.endSpeed, 3),
      accelerationMs2: round(segment.accelerationMs2, 3),
      forceN: round(segment.forceN, 1),
      regenerative: segment.regenerative,
      speedRpm: round(segment.speedRpm, 1),
      torqueNm: round(segment.torqueNm, 3),
      axisTorqueNm: round(segment.axisTorqueNm, 3),
      outOfStroke: segment.outOfStroke,
    })),
  }
}
