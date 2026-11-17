import { computed, ref, watch } from 'vue'

import type { SequenceStep } from '../types/sequence'
import { estimateCycle, estimateSteps } from '../utils/timing'
import type { TransitionPicks } from '../utils/timing'
import type { SequenceDocument } from './useSequenceDocument'
import { useSequenceNames } from './useSequenceNames'

/**
 * The estimated times of the sequence on screen, shared by its page's info
 * strip, editor and displacement-step diagram: the variant they are shown
 * for, the transitions the engineer picked for the cycle, and the step
 * durations and cycle time that follow. The picks live only on this page.
 * The steps are the document's on screen unless a caller brings its own.
 */
export function useSequenceTiming(
  doc: SequenceDocument,
  current: () => readonly SequenceStep[] = () => doc.steps.value,
) {
  const names = useSequenceNames(doc)

  /** Null shows the common values. */
  const variantId = ref<number | null>(null)
  const picks = ref<TransitionPicks>({})
  /** The displacement-step diagram sizes its columns by step duration. */
  const timeAxis = ref(false)

  // A pick for a transition that no longer exists falls back to the first.
  watch(
    current,
    (steps) => {
      const kept = Object.entries(picks.value).filter(([stepKey, transitionKey]) =>
        steps.some((step) => step.key === stepKey && (step.transitions ?? []).some((tr) => tr.key === transitionKey)),
      )
      if (kept.length !== Object.keys(picks.value).length) picks.value = Object.fromEntries(kept)
    },
  )

  const steps = computed(() => estimateSteps(current(), names.deviceById.value, variantId.value, picks.value))
  const cycle = computed(() => estimateCycle(current(), names.deviceById.value, variantId.value, picks.value))

  function setVariant(id: number | null): void {
    variantId.value = id
  }

  function toggleTimeAxis(): void {
    timeAxis.value = !timeAxis.value
  }

  function pick(stepKey: string, transitionKey: string): void {
    picks.value = { ...picks.value, [stepKey]: transitionKey }
  }

  /** The transition the picked pass leaves a step through. */
  function pickedTransition(stepKey: string): string | null {
    const step = current().find((s) => s.key === stepKey)
    const transitions = step?.transitions ?? []
    return (transitions.find((tr) => tr.key === picks.value[stepKey]) ?? transitions[0])?.key ?? null
  }

  return { names, variantId, picks, timeAxis, steps, cycle, setVariant, toggleTimeAxis, pick, pickedTransition }
}

export type SequenceTiming = ReturnType<typeof useSequenceTiming>
