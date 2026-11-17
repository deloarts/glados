/**
 * Minimum gaps against crushing after ISO 13854:2017, Table 1, in our own
 * transcription. A gap at least this wide keeps the body part from being
 * crushed between two parts that close on each other.
 */
import type { BodyPart } from './types'

export const MINIMUM_GAPS: Readonly<Record<BodyPart, number>> = {
  body: 500,
  head: 300,
  leg: 180,
  foot: 120,
  arm: 120,
  hand: 100,
  toes: 50,
  finger: 25,
}

/** Toes are only protected by 50 mm where the step above them is at most this deep (Table 1, figure). */
export const TOE_STEP_DEPTH = 50
