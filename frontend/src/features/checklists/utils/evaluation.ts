import { itemPosition } from './definitions'
import { PROBLEM_ANSWERS } from './types'
import type { Answer, ChecklistDefinition, ChecklistItem, ChecklistState } from './types'

export interface AnswerCounts {
  total: number
  answered: number
  open: number
  na: number
  yes: number
  no: number
  defect: number
}

/**
 * The overall result: failed as soon as one item is "no" or "defect", even
 * while others are unanswered, so a finding never hides behind an open
 * checklist; open while items remain unanswered without findings; passed
 * once every item is answered without findings. The backend computes the
 * same verdict from the stored answers.
 */
export type Verdict = 'passed' | 'open' | 'failed'

export interface Problem {
  id: string
  /** Section and position, for example `1.2/10.1`. */
  position: string
  answer: Answer
  remark: string
}

export function isProblem(answer: Answer | undefined): boolean {
  return answer !== undefined && PROBLEM_ANSWERS.includes(answer)
}

export function countAnswers(
  items: readonly ChecklistItem[],
  answers: Readonly<Record<string, Answer>>,
): AnswerCounts {
  const counts: AnswerCounts = { total: items.length, answered: 0, open: 0, na: 0, yes: 0, no: 0, defect: 0 }
  for (const item of items) {
    const answer = answers[item.id]
    if (answer === undefined) {
      counts.open += 1
    } else {
      counts.answered += 1
      counts[answer] += 1
    }
  }
  return counts
}

export function verdictOf(counts: AnswerCounts): Verdict {
  if (counts.no + counts.defect > 0) return 'failed'
  return counts.open > 0 ? 'open' : 'passed'
}

/** Share of answered items in whole percent, rounded down so 100 means complete. */
export function completionPercent(counts: AnswerCounts): number {
  return counts.total === 0 ? 100 : Math.floor((counts.answered / counts.total) * 100)
}

/** Every item answered "no" or "defect", in checklist order, with its remark. */
export function problemsOf(definition: ChecklistDefinition, state: ChecklistState): Problem[] {
  return definition.items.flatMap((item) => {
    const answer = state.answers[item.id]
    if (answer === undefined || !isProblem(answer)) return []
    return [{ id: item.id, position: itemPosition(definition, item), answer, remark: state.remarks[item.id] ?? '' }]
  })
}

/**
 * Ids of the findings without a remark, in checklist order. A checklist is
 * only released, or counted as finished, once this is empty and every item
 * is answered.
 */
export function findingsWithoutRemark(definition: ChecklistDefinition, state: ChecklistState): string[] {
  return problemsOf(definition, state)
    .filter((problem) => problem.remark.trim() === '')
    .map((problem) => problem.id)
}
