import { afterEach, describe, expect, it } from 'vitest'

import { i18n } from '@/core/i18n'
import deAT from '@/core/i18n/locales/tools/safetyDistance.de-AT'
import enGB from '@/core/i18n/locales/tools/safetyDistance.en-GB'
import { calculateSafetyDistance, safetyDistanceSnapshot } from '../calculate'
import { emptySafetyDistanceInputs } from '../inputs'
import { sampleSafetyDistanceInputs } from '@/features/tools/__tests__/fixtures'
import { summarizeSafetyDistance } from '../summary'
import {
  CALC_STEP_KEYS,
  ESPE_DEVICES,
  REACH_PATHS,
  RESPONSE_TIME_COMPONENTS,
  SAFETY_DISTANCE_MODES,
  SAFETY_MESSAGE_CODES,
} from '../types'
import type { SafetyDistanceInputs } from '../types'

const t = (key: string, params?: Record<string, unknown>) => i18n.global.t(key, params ?? {})

function snapshot(change: (inputs: SafetyDistanceInputs) => void = () => {}): Record<string, unknown> {
  const inputs = sampleSafetyDistanceInputs()
  change(inputs)
  return safetyDistanceSnapshot(inputs, calculateSafetyDistance(inputs))
}

afterEach(() => {
  i18n.global.locale.value = 'enGB'
})

describe('summarizeSafetyDistance', () => {
  it('names the device and S', () => {
    expect(summarizeSafetyDistance(snapshot(), t)).toBe('Light curtain d = 14 mm, S = 200 mm')
    expect(
      summarizeSafetyDistance(
        snapshot((i) => {
          i.mode = 'holdToRun'
          i.holdToRun.actuation = 'foot'
        }),
        t,
      ),
    ).toBe('Foot operated control, S = 2660 mm')
  })

  it('rounds S up to 0.1 mm and formats it in the UI language', () => {
    const results = { ...snapshot((i) => (i.mode = 'twoHand')), s: 1756.44 }
    expect(summarizeSafetyDistance(results, t)).toBe('Two-hand control, S = 1756.5 mm')
    i18n.global.locale.value = 'deAT'
    const german = new Intl.NumberFormat('de-AT', { maximumFractionDigits: 1, useGrouping: false }).format(1756.5)
    expect(summarizeSafetyDistance(results, t)).toBe(`${deAT.summary.twoHand}, S = ${german} mm`)
  })

  it('says when there is no valid distance', () => {
    const results = snapshot((i) => (i.espe.bottomEdge = 400))
    expect(results.s).toBeNull()
    expect(summarizeSafetyDistance(results, t)).toBe('Light curtain d = 14 mm, no valid distance')
  })

  it('stays neutral while fields are empty', () => {
    const inputs = emptySafetyDistanceInputs()
    const results = safetyDistanceSnapshot(inputs, calculateSafetyDistance(inputs))
    expect(summarizeSafetyDistance(results, t)).toBe('New safety distance')
  })

  it('gives an empty string for an unexpected shape', () => {
    expect(summarizeSafetyDistance({}, t)).toBe('')
    expect(summarizeSafetyDistance({ mode: 'espe', inputs: 'curtain' }, t)).toBe('')
    expect(summarizeSafetyDistance({ mode: 'laser', inputs: {} }, t)).toBe('')
    expect(summarizeSafetyDistance({ mode: 'espe', inputs: { device: 'curtain' }, s: 200 }, t)).toBe('')
  })
})

describe('snapshot', () => {
  it('holds the inputs used, every intermediate value, K, S and the findings as plain data', () => {
    const results = snapshot((i) => (i.espe.bottomEdge = 20))
    expect(JSON.parse(JSON.stringify(results))).toEqual(results)
    expect(results).toMatchObject({
      mode: 'espe',
      inputs: { device: 'curtain', detection: 14, bottomEdge: 20, responseTime: { method: 'direct', t: 0.1 } },
      values: { reachThrough: 0, reachUnder: 160, reachCombined: 160, withHandSpeed: 360 },
      k: 2000,
      s: 360,
    })
    expect(results.paths).toContainEqual({ path: 'under', ok: true, reach: 160, k: 1600, s: 320 })
  })
})

// The tab builds these keys at runtime, so the parity check of the locale
// files cannot see them; this keeps every one of them translated.
describe('locale coverage', () => {
  type Tree = Record<string, unknown>

  function flatten(tree: Tree, prefix = ''): string[] {
    return Object.entries(tree).flatMap(([key, value]) =>
      value && typeof value === 'object' ? flatten(value as Tree, `${prefix}${key}.`) : [`${prefix}${key}`],
    )
  }

  function lookup(tree: Tree, path: string): unknown {
    return path.split('.').reduce<unknown>((node, key) => (node as Tree | undefined)?.[key], tree)
  }

  it('has the same keys in English and German', () => {
    expect(flatten(deAT).sort()).toEqual(flatten(enGB).sort())
  })

  it('translates every message, step, path, mode, device and time component', () => {
    const keys = [
      ...SAFETY_MESSAGE_CODES.map((code) => `messages.${code}`),
      ...CALC_STEP_KEYS.map((key) => `steps.${key}`),
      ...REACH_PATHS.map((path) => `paths.${path}`),
      ...SAFETY_DISTANCE_MODES.flatMap((mode) => [`modes.${mode}`, `modeDescriptions.${mode}`]),
      ...ESPE_DEVICES.flatMap((device) => [`devices.${device}`, `deviceHints.${device}`]),
      ...RESPONSE_TIME_COMPONENTS.map((component) => `responseTime.components.${component}`),
    ]
    const missing = keys.filter((key) => typeof lookup(enGB, key) !== 'string' || typeof lookup(deAT, key) !== 'string')
    expect(missing).toEqual([])
  })
})
