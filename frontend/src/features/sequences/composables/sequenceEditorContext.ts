import { inject, provide } from 'vue'
import type { ComputedRef, InjectionKey } from 'vue'

import type { SequenceNames } from './useSequenceNames'
import type { SequenceTiming } from './useSequenceTiming'

/**
 * What every part of the sequence editor needs and the editor provides
 * once: the names of devices, positions and variants, whether the steps can
 * be changed now, the step numbers by key, and the estimated times.
 */
export interface SequenceEditorContext {
  names: SequenceNames
  readonly: ComputedRef<boolean>
  /** The step number shown for a step key, counting from 1. */
  stepNumber: (key: string) => number | null
  stepOptions: ComputedRef<Array<{ key: string; label: string }>>
  timing: SequenceTiming
}

const KEY: InjectionKey<SequenceEditorContext> = Symbol('sequenceEditor')

export function provideSequenceEditor(context: SequenceEditorContext): void {
  provide(KEY, context)
}

export function useSequenceEditor(): SequenceEditorContext {
  const context = inject(KEY)
  if (!context) throw new Error('useSequenceEditor needs a SequenceEditor around it.')
  return context
}
