import type { Schemas } from '@/core/api/generated'

export type PauseCause = Schemas['PauseCause']

// Mirrors the backend's PauseCause value object (pause_cause.py). The pause
// dialog reads its options from here and the lot detail its labels, so a
// later cause needs one edit on this side.
export const PAUSE_CAUSES: PauseCause[] = [
  'waiting_for_material',
  'waiting_for_tool',
  'waiting_for_drawing',
  'waiting_for_qa',
  'machine_fault',
  'other_work',
  'end_of_shift',
]

export function pauseCauseLabelKey(cause: PauseCause): string {
  return `productionQueue.pause.causes.${cause}`
}
