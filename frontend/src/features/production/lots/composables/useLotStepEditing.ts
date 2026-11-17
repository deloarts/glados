import { type Ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useErrorToast } from '@/core/composables/useErrorToast'
import { useFabricationMethodsStore } from '@/features/fabrication-methods'
import { useInspectionMethodsStore } from '@/features/inspection-methods'
import { useProductionLotDetailStore } from '../stores/productionLotDetailStore'

import type { AppendedStep, LotStepPatch } from './useLotStructureDraft'
import type { LotStepResponse } from '../../types/productionLotsResponse'

export interface LotStepEditingProps {
  lotId: number
  staged?: boolean
}

// Staged mode emits these instead of writing; the host's draft writes the
// whole structure on Save.
export interface LotStepEditingIntents {
  editStep: (stepId: number, patch: LotStepPatch) => void
  removeStep: (stepId: number) => void
  appendStep: (step: AppendedStep) => void
  reorderPositions: (orderedPositionIds: number[]) => void
}

/**
 * Step edits of the lot step list: field changes, removing a step, appending
 * a new position and reordering positions by drag.
 */
export function useLotStepEditing(
  props: LotStepEditingProps,
  rows: Ref<LotStepResponse[]>,
  intents: LotStepEditingIntents,
) {
  const { t } = useI18n()
  const { withErrorToast } = useErrorToast()
  const fabricationMethodsStore = useFabricationMethodsStore()
  const inspectionMethodsStore = useInspectionMethodsStore()
  const detailStore = useProductionLotDetailStore()

  async function onFieldChange(step: LotStepResponse, patch: LotStepPatch): Promise<void> {
    if (props.staged) {
      intents.editStep(step.id, patch)
      return
    }
    const succeeded = await withErrorToast(
      async () => {
        await detailStore.updateStep(props.lotId, step.id, {
          fabrication_method_id: step.fabrication_method_id,
          inspection_method_id: step.inspection_method_id,
          note: step.note,
          estimated_setup_minutes: step.estimated_setup_minutes,
          estimated_minutes_per_piece: step.estimated_minutes_per_piece,
          ...patch,
        })
        return true
      },
      { summary: t('production.lots.detail.steps.updateError') },
    )
    if (!succeeded) await detailStore.refetch()
  }

  async function removeStep(step: LotStepResponse): Promise<void> {
    if (props.staged) {
      intents.removeStep(step.id)
      return
    }
    await withErrorToast(() => detailStore.removeStep(props.lotId, step.id), {
      summary: t('production.lots.detail.steps.deleteError'),
    })
  }

  // Both add actions append a new position at the end of the lot. That is
  // the only placement valid for either role, since an inspection step must
  // be alone in its position. The method defaults to the first active one.
  async function appendStepPosition(step: AppendedStep | null): Promise<void> {
    if (!step) return
    if (props.staged) {
      intents.appendStep(step)
      return
    }
    await withErrorToast(
      () =>
        detailStore.appendPosition(props.lotId, {
          steps: [
            {
              note: null,
              estimated_setup_minutes: null,
              estimated_minutes_per_piece: null,
              ...step,
            },
          ],
        }),
      { summary: t('production.lots.detail.steps.addError') },
    )
  }

  async function addStep(): Promise<void> {
    const firstMethod = fabricationMethodsStore.activeItems[0]
    await appendStepPosition(
      firstMethod ? { role: 'fabrication', fabrication_method_id: firstMethod.id } : null,
    )
  }

  async function addInspectionStep(): Promise<void> {
    const firstMethod = inspectionMethodsStore.activeItems[0]
    await appendStepPosition(
      firstMethod ? { role: 'inspection', inspection_method_id: firstMethod.id } : null,
    )
  }

  // The drag handle spans a position but OpenVue reorders one row, so the new
  // order is rebuilt per position; the backend needs each position's steps
  // contiguous.
  async function onRowReorder(event: {
    value: LotStepResponse[]
    dragIndex: number
    dropIndex: number
  }): Promise<void> {
    const steps = rows.value
    const draggedPositionId = steps[event.dragIndex]?.position_id
    const targetPositionId = steps[event.dropIndex]?.position_id
    if (draggedPositionId === undefined || targetPositionId === undefined) return
    if (draggedPositionId === targetPositionId) return

    const positionOrder = [...new Set(steps.map((s) => s.position_id))]
    const from = positionOrder.indexOf(draggedPositionId)
    positionOrder.splice(from, 1)
    // Dragging downwards lands after the target, upwards before it.
    const insertAt =
      positionOrder.indexOf(targetPositionId) + (event.dragIndex < event.dropIndex ? 1 : 0)
    positionOrder.splice(insertAt, 0, draggedPositionId)

    if (props.staged) {
      intents.reorderPositions(positionOrder)
      return
    }

    const orderedStepIds = positionOrder.flatMap((positionId) =>
      steps.filter((s) => s.position_id === positionId).map((s) => s.id),
    )

    const succeeded = await withErrorToast(
      async () => {
        await detailStore.reorderSteps(props.lotId, orderedStepIds)
        return true
      },
      { summary: t('production.lots.detail.steps.reorderError') },
    )
    if (!succeeded) await detailStore.refetch()
  }

  return { onFieldChange, removeStep, addStep, addInspectionStep, onRowReorder }
}
