import { sortedBySequence } from './sequence'

// The steps right before and after a step in the lot's sequence, for the
// material-flow display of the planned date dialog.
export interface StepNeighbors<T> {
  prevStep: T | null
  nextStep: T | null
}

export function findStepNeighbors<T extends { id: number; sequence: number }>(
  steps: T[],
  stepId: number,
): StepNeighbors<T> {
  const sorted = sortedBySequence(steps)
  const index = sorted.findIndex((s) => s.id === stepId)
  if (index === -1) return { prevStep: null, nextStep: null }
  return {
    prevStep: index > 0 ? sorted[index - 1]! : null,
    nextStep: index < sorted.length - 1 ? sorted[index + 1]! : null,
  }
}
