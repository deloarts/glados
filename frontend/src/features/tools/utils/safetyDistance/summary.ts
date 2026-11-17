import { localeTag } from '@/core/utils/dates'
import { finiteNumberOrNull, plainRecordOrNull } from '@/core/utils/guards'

import { numberOptions } from './format'
import { roundUp } from './inputs'
import { BODY_PARTS, OPENING_SHAPES } from './types'
import type { BodyPart, OpeningShape } from './types'

function formatted(value: number): string {
  return new Intl.NumberFormat(localeTag(), numberOptions(1)).format(value)
}

const PREFIX = 'tools.safetyDistance.summary'
const FIELDS = 'tools.safetyDistance.fields'

function head(mode: string, inputs: Record<string, unknown>, t: (key: string, params?: Record<string, unknown>) => string): string {
  const de = finiteNumberOrNull(inputs.detection)
  switch (mode) {
    case 'espe':
      if (inputs.device === 'curtain' && de !== null) return t(`${PREFIX}.curtain`, { de: formatted(de) })
      if (inputs.device === 'multiBeam') return t(`${PREFIX}.multiBeam`)
      if (inputs.device === 'singleBeam') return t(`${PREFIX}.singleBeam`)
      return ''
    case 'parallel':
      return de === null ? '' : t(`${PREFIX}.parallel`, { de: formatted(de) })
    case 'twoHand':
      return t(inputs.encroachmentPrevented === true ? `${PREFIX}.twoHandPrevented` : `${PREFIX}.twoHand`)
    case 'holdToRun':
      return inputs.actuation === 'foot' ? t(`${PREFIX}.holdToRunFoot`) : t(`${PREFIX}.holdToRunHand`)
    case 'guard':
      return t(inputs.locking === true ? `${PREFIX}.guardLocking` : `${PREFIX}.guard`)
    case 'structure': {
      const hps = finiteNumberOrNull(inputs.structureHeight)
      const hh = finiteNumberOrNull(inputs.hazardHeight)
      return hps === null || hh === null ? '' : t(`${PREFIX}.structure`, { hps: formatted(hps), hh: formatted(hh) })
    }
    case 'opening': {
      const e = finiteNumberOrNull(inputs.size)
      const shape = typeof inputs.shape === 'string' ? inputs.shape : ''
      if (e === null || !OPENING_SHAPES.includes(shape as OpeningShape)) return ''
      const label = t(`${PREFIX}.opening.${shape}`, { e: formatted(e) })
      return inputs.limb === 'lower' ? t(`${PREFIX}.openingLower`, { opening: label }) : label
    }
    case 'crushing': {
      const part = typeof inputs.bodyPart === 'string' ? inputs.bodyPart : ''
      return BODY_PARTS.includes(part as BodyPart) ? t(`${PREFIX}.crushing`, { part: t(`${FIELDS}.bodyPart.${part}`) }) : ''
    }
    default:
      return ''
  }
}

/** The result as the summary names it: S, the safety distance of ISO 13857 or the minimum gap. */
function distanceText(mode: string, s: number, t: (key: string, params?: Record<string, unknown>) => string): string {
  const value = formatted(roundUp(s, 1))
  if (mode === 'structure' || mode === 'opening') return t(`${PREFIX}.safetyDistance`, { s: value })
  if (mode === 'crushing') return t(`${PREFIX}.minimumGap`, { s: value })
  return t(`${PREFIX}.distance`, { s: value })
}

const INCOMPLETE = new Set(['missingInputs', 'missingResponseTime'])

function incomplete(results: Record<string, unknown>): boolean {
  const messages = results.messages
  return Array.isArray(messages) && messages.some((m) => INCOMPLETE.has(String(plainRecordOrNull(m)?.code)))
}

/**
 * One line for calculation lists and the default title, such as
 * "Light curtain d = 14 mm, S = 200 mm" or "Square opening 40 mm, safety
 * distance 200 mm". The distance is rounded up to 0.1 mm like on the tab.
 * While fields are still empty the line is a neutral "New safety distance".
 * A snapshot of an unexpected shape gives an empty string.
 */
export function summarizeSafetyDistance(
  results: Record<string, unknown>,
  t: (key: string, params?: Record<string, unknown>) => string,
): string {
  const mode = results.mode
  const inputs = plainRecordOrNull(results.inputs)
  if (typeof mode !== 'string' || !inputs) return ''
  if (incomplete(results)) return t(`${PREFIX}.new`)
  const label = head(mode, inputs, t)
  if (!label) return ''
  const s = finiteNumberOrNull(results.s)
  const distance = s === null ? t(`${PREFIX}.noResult`) : distanceText(mode, s, t)
  return `${label}, ${distance}`
}
