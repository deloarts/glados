import { completionPercent, countAnswers, problemsOf, verdictOf } from './evaluation'
import type { AnswerCounts, Problem, Verdict } from './evaluation'
import type { ChecklistDefinition, ChecklistState, ChecklistType, LegalBasis } from './types'

/**
 * What the summary card shows for the answers on screen: counts,
 * completion, verdict and the findings in checklist order. It holds codes
 * and ids only, never translated text.
 */
export type ChecklistResults = {
  type: ChecklistType
  legalBasis: LegalBasis
  counts: AnswerCounts
  completion: number
  verdict: Verdict
  problems: Problem[]
}

export function checklistResults(definition: ChecklistDefinition, state: ChecklistState): ChecklistResults {
  const counts = countAnswers(definition.items, state.answers)
  return {
    type: definition.type,
    legalBasis: state.header.legalBasis,
    counts,
    completion: completionPercent(counts),
    verdict: verdictOf(counts),
    problems: problemsOf(definition, state),
  }
}
