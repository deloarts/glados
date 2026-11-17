import type {
  SequenceAction,
  SequenceConditionKind,
  SequenceConditionTerm,
  SequenceStep,
  SequenceTransition,
} from '../types/sequence'
import { TARGET_NEXT } from '../types/sequence'
import { newKey } from './steps'

/** New, empty parts of a sequence in the canonical shape of steps.ts. */

export function newTerm(kind: SequenceConditionKind): SequenceConditionTerm {
  return {
    kind,
    device_id: null,
    position_id: null,
    comparator: kind === 'device_value' ? 'ge' : null,
    value: null,
    step_key: null,
    duration_ms: null,
    text: null,
  }
}

export function newAction(kind: SequenceAction['kind'] = 'device'): SequenceAction {
  return {
    key: newKey('a'),
    kind,
    qualifier: 'stored',
    device_id: null,
    position_id: null,
    value: null,
    text: null,
    description: null,
    condition: [],
    duration_ms: null,
  }
}

export function newTransition(target: string = TARGET_NEXT): SequenceTransition {
  return { key: newKey('t'), target, condition: [] }
}

export function newStep(): SequenceStep {
  return {
    key: newKey('s'),
    description: null,
    timeout_ms: null,
    expected_duration_ms: null,
    actions: [newAction()],
    transitions: [newTransition()],
  }
}
