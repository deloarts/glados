/**
 * Safety distances: separation distances of protective devices after ISO
 * 13855:2024, with the reach distances it takes from ISO 13857:2019 and the
 * two-hand control checks of ISO 13851:2019; safety distances against
 * reaching over structures and through openings after ISO 13857:2019; and
 * minimum gaps against crushing after ISO 13854:2017. The tables hold our own
 * transcription of the standards' numeric values.
 */

/** Raise when the saved input record of the tool changes shape. */
export const SAFETY_DISTANCE_INPUT_VERSION = 2
/** Raise when the same inputs would give a different result. */
export const SAFETY_DISTANCE_ENGINE_VERSION = 2

export { calculateSafetyDistance, safetyDistanceSnapshot, usesSupplement } from './calculate'
export { emptySafetyDistanceInputs } from './inputs'
export { decodeSafetyDistanceInputs, encodeSafetyDistanceInputs, SAFETY_DISTANCE_INPUT_KEYS } from './inputRecord'
export { summarizeSafetyDistance } from './summary'
