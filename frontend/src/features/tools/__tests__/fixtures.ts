/**
 * Filled inputs of the calculation tools for specs. The tools themselves start
 * blank; these samples give the engines, decoders and reports realistic
 * figures to work on.
 */

import type {
  DriveSizingInput,
  DriveSizingSettings,
  MoveSegmentInput,
  PauseSegmentInput,
  SegmentInput,
} from '../utils/driveSizing/model'
import type { SafetyDistanceInputs } from '../utils/safetyDistance/types'

export const SAMPLE_SETTINGS: Readonly<DriveSizingSettings> = {
  orientation: 'vertical',
  angleDeg: 30,
  strokeMm: 1200,
  transmission: 'rack',
  diameterMm: 91.67,
  pitchMm: 10,
  transmissionEfficiency: 0.9,
  axisTorqueLimitNm: null,
  axisInertiaKgCm2: 0,
  ratio: 12,
  gearboxEfficiency: 0.95,
  gearboxInertiaKgCm2: 0,
  ratedSpeedRpm: 2000,
  maxSpeedRpm: null,
  ratedTorqueNm: 5.98,
  maxTorqueNm: 18,
  motorInertiaKgCm2: 4.5,
  brakeTorqueNm: 13,
  brakeSafetyFactor: 2,
  carriageMassKg: 100,
  payloadMassKg: 40,
  friction: 0.1,
  processForceN: 0,
}

function move(
  distanceMm: number,
  startSpeed: number,
  endSpeed: number,
  payload: boolean,
): MoveSegmentInput {
  return { kind: 'move', distanceMm, startSpeed, endSpeed, payload }
}

function pause(durationS: number, payload: boolean, brake: boolean): PauseSegmentInput {
  return { kind: 'pause', durationS, payload, brake }
}

/**
 * A vertical pick-and-place cycle: up empty to 700 mm, pick up the payload,
 * up to 1100 mm, wait, down with the payload to 200 mm, drop it and return
 * empty to 0 mm. Every move starts and ends at the speed of its neighbours.
 */
export const SAMPLE_SEGMENTS: readonly SegmentInput[] = [
  move(200, 0, 0.5, false),
  move(300, 0.5, 0.5, false),
  move(200, 0.5, 0, false),
  pause(1, false, true),
  move(100, 0, 0.3, true),
  move(200, 0.3, 0.3, true),
  move(100, 0.3, 0, true),
  pause(4, true, false),
  move(-250, 0, 0.3, true),
  move(-400, 0.3, 0.3, true),
  move(-250, 0.3, 0, true),
  pause(1, false, false),
  move(-50, 0, 0.5, false),
  move(-100, 0.5, 0.5, false),
  move(-50, 0.5, 0, false),
  pause(3, false, false),
]

/** The sample axis with its pick-and-place cycle. */
export function sampleDriveSizingInput(): DriveSizingInput {
  return { ...SAMPLE_SETTINGS, segments: [...SAMPLE_SEGMENTS] }
}

/**
 * A filled safety distance form: a finger protecting light curtain standing
 * on the floor in front of a hazard at table height, with a known response
 * time. Every other mode is filled too, so switching the mode gives a result
 * there as well.
 */
export function sampleSafetyDistanceInputs(): SafetyDistanceInputs {
  return {
    mode: 'espe',
    responseTime: {
      method: 'direct',
      direct: 0.1,
      tI: null,
      tL: null,
      tO: null,
      tD: null,
      tR: null,
      tM: null,
      tF: null,
      tS: null,
      cold: [],
      warm: [],
    },
    supplement: 0,
    espe: {
      device: 'curtain',
      detection: 14,
      topEdge: 1800,
      bottomEdge: 0,
      hazardHeight: 1000,
      industrial: true,
      restart: false,
      structureAbove: false,
      structureTop: null,
      structureBelow: false,
      structureGap: null,
      beamHeights: [200, 500, 800, 1100],
      openingHeight: null,
      stepArrangement: false,
      stepHeight: null,
    },
    parallel: {
      detection: 50,
      fieldHeight: 150,
      fieldDepth: 1200,
      obstacleGap: null,
      standingDetected: false,
    },
    twoHand: { encroachmentPrevented: false, type: 'IIIC', actuatorGap: 550 },
    holdToRun: { actuation: 'hand' },
    guard: {
      locking: false,
      unlockDelay: null,
      reachThroughOwn: false,
      reachThrough: null,
      openingMethod: 'direct',
      openingShape: 'slot',
      slotLength: null,
      opening: 20,
      guardWidth: null,
      angle: null,
      guardThickness: null,
    },
    structure: { hazardHeight: 1400, structureHeight: 1800, distance: null, lowRisk: false },
    opening: { shape: 'square', size: 40, slotLength: null, limb: 'upper', children: false, distance: null },
    crushing: { bodyPart: 'finger', gap: 30 },
  }
}
