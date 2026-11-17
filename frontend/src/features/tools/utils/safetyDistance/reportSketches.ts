import type { Component } from 'vue'

import type { AppLocale } from '@/core/i18n'
import { renderComponentSvg } from '@/shared/reports'
import type { RenderedDrawing } from '@/shared/reports'
import SafetyDistanceBeamSketch from '../../components/SafetyDistanceBeamSketch.vue'
import SafetyDistanceCrushingSketch from '../../components/SafetyDistanceCrushingSketch.vue'
import SafetyDistanceEspeSketch from '../../components/SafetyDistanceEspeSketch.vue'
import SafetyDistanceHingeSketch from '../../components/SafetyDistanceHingeSketch.vue'
import SafetyDistanceOpeningSketch from '../../components/SafetyDistanceOpeningSketch.vue'
import SafetyDistanceParallelSketch from '../../components/SafetyDistanceParallelSketch.vue'
import SafetyDistanceReachSketch from '../../components/SafetyDistanceReachSketch.vue'
import SafetyDistanceStructureSketch from '../../components/SafetyDistanceStructureSketch.vue'
import SafetyDistanceTimelineSketch from '../../components/SafetyDistanceTimelineSketch.vue'
import { usesResponseTime } from './calculate'
import type { SafetyDistanceInputs, SafetyDistanceResult } from './types'

/**
 * The sketches of the tab for the report: the same drawings the tab shows
 * for the chosen mode, followed by the timeline of the response time when it
 * is summed from its components.
 */

type Sketch = [Component, Record<string, unknown>]

function sketchesFor(inputs: SafetyDistanceInputs, result: SafetyDistanceResult): Sketch[] {
  const sketches: Sketch[] = []
  switch (inputs.mode) {
    case 'espe':
      sketches.push(
        inputs.espe.device === 'curtain'
          ? [SafetyDistanceEspeSketch, { inputs: inputs.espe, result }]
          : [SafetyDistanceBeamSketch, { inputs: inputs.espe }],
      )
      break
    case 'parallel':
      sketches.push([SafetyDistanceParallelSketch, { inputs: inputs.parallel, result }])
      break
    case 'structure':
      sketches.push([SafetyDistanceStructureSketch, { inputs: inputs.structure, result }])
      break
    case 'opening':
      sketches.push([SafetyDistanceOpeningSketch, { inputs: inputs.opening, result }])
      break
    case 'crushing':
      sketches.push([SafetyDistanceCrushingSketch, { inputs: inputs.crushing, result }])
      break
    default:
      if (inputs.mode === 'guard' && inputs.guard.openingMethod === 'hinged') {
        sketches.push([SafetyDistanceHingeSketch, { inputs: inputs.guard, result }])
      }
      sketches.push([SafetyDistanceReachSketch, { inputs, result }])
  }
  if (usesResponseTime(inputs) && inputs.responseTime.method === 'components') {
    sketches.push([SafetyDistanceTimelineSketch, { inputs: inputs.responseTime }])
  }
  return sketches
}

export async function renderSafetyDistanceSketches(
  inputs: SafetyDistanceInputs,
  result: SafetyDistanceResult,
  locale: AppLocale,
): Promise<RenderedDrawing[]> {
  const drawings: RenderedDrawing[] = []
  // One at a time: each mounts its own small app on the page.
  for (const [component, props] of sketchesFor(inputs, result)) {
    const drawing = await renderComponentSvg(component, props, locale)
    if (drawing) drawings.push(drawing)
  }
  return drawings
}
