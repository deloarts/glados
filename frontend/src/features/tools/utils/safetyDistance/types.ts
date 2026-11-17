/**
 * Inputs and results of the safety distance tool: separation distances of
 * protective devices after ISO 13855:2024, safety distances against reaching
 * hazard zones after ISO 13857:2019 and minimum gaps against crushing after
 * ISO 13854:2017. Lengths are in mm, times in s, speeds in mm/s and angles in
 * degrees, as in the standards, so K·T comes out in mm without conversion.
 */

/** What a distance is calculated for: a protective device, a protective structure or a crushing point. */
export const SAFETY_DISTANCE_MODES = [
  'espe',
  'parallel',
  'twoHand',
  'holdToRun',
  'guard',
  'structure',
  'opening',
  'crushing',
] as const
export type SafetyDistanceMode = (typeof SAFETY_DISTANCE_MODES)[number]

/** The modes grouped by the standard they follow, in the order the tool offers them. */
export const MODE_GROUPS = {
  devices: ['espe', 'parallel', 'twoHand', 'holdToRun', 'guard'],
  reach: ['structure', 'opening'],
  crushing: ['crushing'],
} as const satisfies Record<string, readonly SafetyDistanceMode[]>
export type ModeGroup = keyof typeof MODE_GROUPS

export function modeGroup(mode: SafetyDistanceMode): ModeGroup {
  if ((MODE_GROUPS.reach as readonly string[]).includes(mode)) return 'reach'
  if (mode === 'crushing') return 'crushing'
  return 'devices'
}

/** The standards the tool draws on. A reference without a standard is to ISO 13855. */
export const STANDARDS = {
  iso13855: 'ISO 13855:2024',
  iso13857: 'ISO 13857:2019',
  iso13854: 'ISO 13854:2017',
  iso13851: 'ISO 13851:2019',
} as const
export type StandardId = keyof typeof STANDARDS

/** Shapes of a regular opening after ISO 13857:2019; e is the slot width, the side or the diameter. */
export const OPENING_SHAPES = ['slot', 'square', 'round'] as const
export type OpeningShape = (typeof OPENING_SHAPES)[number]

/** Which limbs can reach an opening: Tables 4 and 5 of ISO 13857 for the upper limbs, Table 7 for the lower. */
export const LIMBS = ['upper', 'lower'] as const
export type Limb = (typeof LIMBS)[number]

/** Body parts of ISO 13854:2017, Table 1, largest first; `hand` stands for hand, wrist and fist. */
export const BODY_PARTS = ['body', 'head', 'leg', 'foot', 'arm', 'hand', 'toes', 'finger'] as const
export type BodyPart = (typeof BODY_PARTS)[number]

/** Types of two-hand control devices after ISO 13851:2019, Table 1. */
export const TWO_HAND_TYPES = ['I', 'II', 'IIIA', 'IIIB', 'IIIC'] as const
export type TwoHandType = (typeof TWO_HAND_TYPES)[number]

/** Kinds of electro-sensitive protective equipment approached at a right angle (clause 8). */
export const ESPE_DEVICES = ['curtain', 'multiBeam', 'singleBeam'] as const
export type EspeDevice = (typeof ESPE_DEVICES)[number]

/** How the overall system response time T is obtained (5.4 and Annex B). */
export const RESPONSE_TIME_METHODS = ['direct', 'components', 'measured'] as const
export type ResponseTimeMethod = (typeof RESPONSE_TIME_METHODS)[number]

/** The time components summed by equation (3), in its order, and the sampling interval t_S that equation (7) adds. */
export const RESPONSE_TIME_COMPONENTS = ['tI', 'tL', 'tO', 'tD', 'tR', 'tM', 'tF', 'tS'] as const
export type ResponseTimeComponent = (typeof RESPONSE_TIME_COMPONENTS)[number]

export const MEASUREMENT_CONDITIONS = ['cold', 'warm'] as const
export type MeasurementCondition = (typeof MEASUREMENT_CONDITIONS)[number]

export const HOLD_TO_RUN_ACTUATIONS = ['hand', 'foot'] as const
export type HoldToRunActuation = (typeof HOLD_TO_RUN_ACTUATIONS)[number]

export const OPENING_METHODS = ['direct', 'hinged'] as const
export type OpeningMethod = (typeof OPENING_METHODS)[number]

/**
 * The response time inputs of every method are kept side by side, so
 * switching the method and back loses nothing. `tF` belongs to both the sum
 * of components (equation 3) and the measured time (equation 5).
 */
export interface ResponseTimeInputs extends Record<ResponseTimeComponent, number | null> {
  method: ResponseTimeMethod
  direct: number | null
  cold: number[]
  warm: number[]
}

export interface EspeInputs {
  device: EspeDevice
  /** Effective detection capability d_e of a light curtain. */
  detection: number | null
  /** Effective top edge of the detection zone, H_DT. */
  topEdge: number | null
  /** Bottom edge of the detection zone, H_DB. */
  bottomEdge: number | null
  /** Height of the nearest point of the hazard zone, H_H. */
  hazardHeight: number | null
  industrial: boolean
  /** The light curtain also starts the next machine cycle (8.6). */
  restart: boolean
  structureAbove: boolean
  /** Top edge of the structure above the field, H_GT, which sets D_GO through ISO 13857:2019, Table 2. */
  structureTop: number | null
  structureBelow: boolean
  /** Bottom edge of the structure below the field, H_GB. */
  structureGap: number | null
  /** Beam heights of a multi-beam device above the reference plane. */
  beamHeights: number[]
  /** Height of the protected opening, only needed for the low two-beam arrangement of Annex C. */
  openingHeight: number | null
  /** Two beams in front of a step higher than 300 mm (8.3.5). */
  stepArrangement: boolean
  /** Height H_S of the step above the reference plane. */
  stepHeight: number | null
}

export interface ParallelInputs {
  detection: number | null
  /** Height of the detection zone above the reference plane, H_D. */
  fieldHeight: number | null
  /** Depth of the detection zone, F_D. */
  fieldDepth: number | null
  /** Gap between the detection zone and the nearest obstacle, G_D. */
  obstacleGap: number | null
  /** A person standing inside the detection zone is detected. */
  standingDetected: boolean
}

export interface TwoHandInputs {
  encroachmentPrevented: boolean
  /** Type after ISO 13851:2019; empty when not checked. */
  type: TwoHandType | null
  /** Clear distance between the two actuators. */
  actuatorGap: number | null
}

export interface HoldToRunInputs {
  actuation: HoldToRunActuation
}

export interface GuardInputs {
  locking: boolean
  /** Unlocking delay of the guard locking device, t_DY. */
  unlockDelay: number | null
  /**
   * D_GT is the user's own value from the risk assessment instead of the one
   * ISO 13857:2019, Table 4 gives for the opening (12.2.1).
   */
  reachThroughOwn: boolean
  /** The user's own D_GT, only used with `reachThroughOwn`. */
  reachThrough: number | null
  openingMethod: OpeningMethod
  /** Shape of a known opening; the gap of a hinged guard is always a slot. */
  openingShape: OpeningShape
  /** Length of a slot shaped known opening; a short slot may reduce D_GT. */
  slotLength: number | null
  /** Opening e before the interlock trips, entered directly. */
  opening: number | null
  /** Width G_W of a hinged guard with a cam operated switch. */
  guardWidth: number | null
  /** Actuation angle ω of the cam operated switch. */
  angle: number | null
  /** Thickness G_T of the guard leaf. */
  guardThickness: number | null
}

/** Reaching over a protective structure such as a fence (ISO 13857:2019, 4.2.1 and 4.2.2). */
export interface StructureInputs {
  /** Height of the nearest point of the hazard zone, h_h. */
  hazardHeight: number | null
  /** Height of the protective structure, h_ps. */
  structureHeight: number | null
  /** Horizontal distance from the structure to the hazard zone as built, s_h; optional. */
  distance: number | null
  /** Severity and probability of harm are both low, so Table 1 applies instead of Table 2. */
  lowRisk: boolean
}

/** Reaching through a regular opening (ISO 13857:2019, 4.2.4 and 4.3). */
export interface OpeningInputs {
  shape: OpeningShape
  /** Slot width, side of a square or diameter of a round opening, e. */
  size: number | null
  /** Length of a slot; a short slot lets the thumb limit the reach. Optional. */
  slotLength: number | null
  limb: Limb
  /** Children from three years on may reach the opening (Table 5); upper limbs only. */
  children: boolean
  /** Distance from the opening to the hazard zone as built, s_r; optional. */
  distance: number | null
}

/** A crushing point between two parts (ISO 13854:2017). */
export interface CrushingInputs {
  /** Largest body part that can get into the crushing point. */
  bodyPart: BodyPart | null
  /** Gap between the parts as built, a; optional. */
  gap: number | null
}

export interface SafetyDistanceInputs {
  mode: SafetyDistanceMode
  responseTime: ResponseTimeInputs
  /** Application dependent supplement Z (5.6); used by the ESPE and parallel modes. */
  supplement: number | null
  espe: EspeInputs
  parallel: ParallelInputs
  twoHand: TwoHandInputs
  holdToRun: HoldToRunInputs
  guard: GuardInputs
  structure: StructureInputs
  opening: OpeningInputs
  crushing: CrushingInputs
}

export type MessageLevel = 'error' | 'warning' | 'info'

/** Every finding the calculation can report; each one is a message of the tool's locale. */
export const SAFETY_MESSAGE_CODES = [
  'missingInputs',
  'missingResponseTime',
  'missingSamplesCold',
  'missingSamplesWarm',
  'fewSamplesCold',
  'fewSamplesWarm',
  'walkingSpeedApplies',
  'minimumApplies',
  'publicSupplementApplies',
  'reachOverRows',
  'reachOverColumn',
  'reachUnderRow',
  'reachUnderStructureRow',
  'edgesInverted',
  'handNotDetected',
  'restartResolution',
  'restartMinimumApplied',
  'restartMinimumMet',
  'topEdgeTooLow',
  'bottomEdgeTooHigh',
  'structureGapTooLarge',
  'structureGoverns',
  'wholeBodyOnly',
  'tooFewBeams',
  'lowestBeamTooHigh',
  'lowestBeamRiskAssessment',
  'highestBeamTooLow',
  'lowOpeningAllowed',
  'lowOpeningOnly',
  'beamSpacingTooLarge',
  'stepArrangement',
  'stepTwoBeams',
  'stepTooLow',
  'stepLowestBeam',
  'stepSpacingTooLarge',
  'annexCMatch',
  'annexCNoMatch',
  'singleBeamPlacement',
  'detectionTooCoarse',
  'fieldTooLow',
  'fieldTooHigh',
  'fieldAboveCrawlHeight',
  'fieldTooShallow',
  'depthReducible',
  'farthestEdge',
  'encroachmentConfirm',
  'measuredFromActuator',
  'openingClamped',
  'openingBodyParts',
  'openingWholeBody',
  'unlockDelayCoversT',
  'measuredFromOpening',
  'structureTopTooLow',
  'structureTopLow',
  'tableRows',
  'tableColumn',
  'gapAsSlot',
  'openingBeyondTable',
  'guardOpeningBeyondTable',
  'reachThroughOwnValue',
  'reachThroughOwnBelowTable',
  'shortSlotReduction',
  'twoHandTypeI',
  'twoHandTypeII',
  'twoHandTypeIIIA',
  'twoHandTypeIIIB',
  'twoHandTypeIIIC',
  'actuatorGapOneHand',
  'actuatorGapElbow',
  'actuatorGapErgonomic',
  'structureTooLow',
  'structureLow',
  'lowRiskTable',
  'outOfReachAbove',
  'structureTooClose',
  'structureHeightForDistance',
  'toesOverhang',
  'distanceMet',
  'openingTooClose',
  'openingWholeBodyAccess',
  'slotNotPermitted',
  'lowerLimbsOnly',
  'childrenTable',
  'largestBodyPart',
  'gapTooSmall',
  'gapLargeEnough',
] as const
export type SafetyMessageCode = (typeof SAFETY_MESSAGE_CODES)[number]

/**
 * A finding of the calculation. `code` names a message of the tool's locale,
 * `params` fills its placeholders. An error means the standard does not cover
 * or permit the configuration, so there is no separation distance.
 */
export interface SafetyMessage {
  code: SafetyMessageCode
  level: MessageLevel
  params?: Record<string, number>
}

/** Where a value comes from; without `standard` in ISO 13855:2024. */
export interface StandardRef {
  standard?: StandardId
  clause: string
  equation?: string
  table?: string
}

export type Unit = 'mm' | 's' | 'mm/s' | '°'

/** Every line the worked calculation can show; each one is labelled in the tool's locale. */
export const CALC_STEP_KEYS = [
  'responseTime',
  'controlTime',
  'machineTime',
  'measuredTime',
  'reachOver',
  'reachThrough',
  'reachUnder',
  'reachOverStructure',
  'reachUnderStructure',
  'reachCombined',
  'withHandSpeed',
  'withWalkingSpeed',
  'minimum',
  'minimumAndSupplement',
  'publicSupplement',
  'separation',
  'restartMinimum',
  'lowestBeam',
  'highestBeam',
  'beamSpacing',
  'minFieldHeight',
  'requiredDepth',
  'hingeGap',
  'opening',
  'reachThroughGuard',
  'remainingTime',
  'horizontalDistance',
  'minStructureHeight',
  'openingReach',
  'minimumGap',
] as const
export type CalcStepKey = (typeof CALC_STEP_KEYS)[number]

/**
 * One line of the worked calculation. `formula` is symbolic, `expression`
 * repeats it with numbers as `{name}` placeholders that the view fills from
 * `args` in the user's number format.
 */
export interface CalcStep {
  key: CalcStepKey
  symbol: string
  formula: string | null
  expression: string | null
  args: Record<string, number>
  value: number
  unit: Unit
  ref: StandardRef | null
  note?: SafetyMessage
}

export interface ConditionStats {
  condition: MeasurementCondition
  n: number
  max: number
  mean: number
  /** Sample standard deviation (n − 1); null below two samples. */
  sd: number | null
  meanPlus3Sd: number | null
  t: number
}

export interface ResponseTimeResult {
  method: ResponseTimeMethod
  t: number | null
  steps: CalcStep[]
  conditions: ConditionStats[]
  messages: SafetyMessage[]
}

export const REACH_PATHS = ['over', 'through', 'under', 'overStructure', 'underStructure'] as const
export type ReachPath = (typeof REACH_PATHS)[number]

/** One way past a vertical detection zone, calculated with its own approach speed rule. */
export interface PathResult {
  path: ReachPath
  ok: boolean
  reach: number | null
  k: number | null
  s: number | null
  ref: StandardRef
}

export interface SafetyDistanceResult {
  mode: SafetyDistanceMode
  /** Symbol of the result: S for a separation distance, s_h or s_r for ISO 13857, a for a gap. */
  symbol: string
  responseTime: ResponseTimeResult
  t: number | null
  supplement: number | null
  k: number | null
  s: number | null
  formula: string
  ref: StandardRef
  steps: CalcStep[]
  paths: PathResult[]
  messages: SafetyMessage[]
}
