import { stepMethodLabel } from '../../utils/lotStepDisplay'

import type { ITask } from '@svar-ui/vue-gantt'
import type { LotResponse, LotStepResponse } from '../../types/productionLotsResponse'

export interface ResolvedPositionSchedule {
  positionId: number
  start: Date
  end: Date
}

export interface LotWithSchedule {
  lot: LotResponse
  schedules: ResolvedPositionSchedule[]
}

// A lot's bar spans its earliest to latest scheduled step. Lots and steps
// without a schedule are dropped instead of shown with a made-up range.
export function buildLotGanttTasks(
  lotsWithSchedule: LotWithSchedule[],
  madeItemLabel: (partNumber: string, revision: string) => string,
): ITask[] {
  const tasks: ITask[] = []

  for (const { lot, schedules } of lotsWithSchedule) {
    if (schedules.length === 0) continue

    const scheduleByPosition = new Map(schedules.map((s) => [s.positionId, s]))
    const scheduledSteps: { step: LotStepResponse; schedule: ResolvedPositionSchedule }[] = []
    for (const step of lot.steps ?? []) {
      const schedule = scheduleByPosition.get(step.position_id)
      if (schedule) scheduledSteps.push({ step, schedule })
    }
    if (scheduledSteps.length === 0) continue

    const lotStart = new Date(Math.min(...scheduledSteps.map((s) => s.schedule.start.getTime())))
    const lotEnd = new Date(Math.max(...scheduledSteps.map((s) => s.schedule.end.getTime())))

    tasks.push({
      id: `lot-${lot.id}`,
      text: `${lot.lot_number} (${madeItemLabel(lot.made_item_part_number, lot.made_item_revision)})`,
      start: lotStart,
      end: lotEnd,
      type: 'summary',
      parent: 0,
      open: false,
      status: lot.status,
    })

    for (const { step, schedule } of scheduledSteps) {
      tasks.push({
        id: `lot-step-${step.id}`,
        text: stepMethodLabel(step),
        start: schedule.start,
        end: schedule.end,
        type: 'task',
        parent: `lot-${lot.id}`,
      })
    }
  }

  return tasks
}
