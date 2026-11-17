import type { AutoPlanAlgorithm } from '../types/scheduleBoardResponse'

// Mirrors the backend's AutoPlanAlgorithm enum, in picker order.
export const AUTO_PLAN_ALGORITHMS: AutoPlanAlgorithm[] = [
  'urgent_first',
  'strict_deadline',
  'fair_queue',
  'balanced_load',
  'critical_ratio',
  'shortest_processing_time',
]

// Spelled out so the i18n keys stay greppable.
const ALGORITHM_I18N_NAMES: Record<AutoPlanAlgorithm, string> = {
  urgent_first: 'urgentFirst',
  strict_deadline: 'strictDeadline',
  fair_queue: 'fairQueue',
  balanced_load: 'balancedLoad',
  critical_ratio: 'criticalRatio',
  shortest_processing_time: 'shortestProcessingTime',
}

// One i18n subtree per algorithm holds the picker and explain texts.
export function algorithmKey(algorithm: AutoPlanAlgorithm, field: string): string {
  return `productionSchedule.autoPlan.algorithms.${ALGORITHM_I18N_NAMES[algorithm]}.${field}`
}
