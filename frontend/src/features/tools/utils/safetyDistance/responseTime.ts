import { MEASUREMENT_CONDITIONS } from './types'
import type {
  CalcStep,
  CalcStepKey,
  ConditionStats,
  MeasurementCondition,
  ResponseTimeInputs,
  ResponseTimeResult,
  SafetyMessage,
} from './types'

/** Annex B asks for at least this many measurements per test condition. */
export const MIN_SAMPLES = 10

/**
 * Evaluates the measurements of one test condition as Annex B.5 does: the
 * larger of the highest measured time and the mean plus three sample
 * standard deviations (n − 1). Every sample counts; Annex B only allows
 * dropping one that is known to be a measurement error, which the tool
 * cannot judge. A single sample has no spread, so its value is used as is.
 */
export function conditionStats(condition: MeasurementCondition, samples: readonly number[]): ConditionStats | null {
  const n = samples.length
  if (n === 0) return null
  const max = Math.max(...samples)
  const mean = samples.reduce((sum, x) => sum + x, 0) / n
  if (n < 2) return { condition, n, max, mean, sd: null, meanPlus3Sd: null, t: max }
  const sd = Math.sqrt(samples.reduce((sum, x) => sum + (x - mean) ** 2, 0) / (n - 1))
  const meanPlus3Sd = mean + 3 * sd
  return { condition, n, max, mean, sd, meanPlus3Sd, t: Math.max(max, meanPlus3Sd) }
}

function step(
  key: CalcStepKey,
  symbol: string,
  formula: string | null,
  expression: string | null,
  args: Record<string, number>,
  value: number,
  clause: string,
  equation?: string,
): CalcStep {
  return { key, symbol, formula, expression, args, value, unit: 's', ref: { clause, equation } }
}

function direct(inputs: ResponseTimeInputs): ResponseTimeResult {
  const t = inputs.direct
  if (t === null) {
    return { method: 'direct', t: null, steps: [], conditions: [], messages: [missing()] }
  }
  return {
    method: 'direct',
    t,
    steps: [step('responseTime', 'T', null, null, {}, t, '5.4')],
    conditions: [],
    messages: [],
  }
}

// An empty component is a part that does not apply to the machine, so it
// counts as zero; equation (3) lets the designer leave such parts out. The
// sampling interval t_S of the controller is the addition of equation (7),
// which clause 8 refers to; with it the sum follows that equation.
function components(inputs: ResponseTimeInputs): ResponseTimeResult {
  const v = (value: number | null) => value ?? 0
  const tI = v(inputs.tI)
  const tL = v(inputs.tL)
  const tO = v(inputs.tO)
  const tD = v(inputs.tD)
  const tR = v(inputs.tR)
  const tM = v(inputs.tM)
  const tF = v(inputs.tF)
  const tS = v(inputs.tS)
  const control = tI + tL + tO
  const machine = tD + tR + tM
  const t = control + machine + tF + tS
  const total =
    tS > 0
      ? step(
          'responseTime',
          'T',
          't_SRP/CS + t_ME + t_F + t_S',
          '{control} + {machine} + {tF} + {tS}',
          { control, machine, tF, tS },
          t,
          '6.1',
          '7',
        )
      : step(
          'responseTime',
          'T',
          't_SRP/CS + t_ME + t_F',
          '{control} + {machine} + {tF}',
          { control, machine, tF },
          t,
          '5.4',
          '3',
        )
  return {
    method: 'components',
    t,
    steps: [
      step('controlTime', 't_SRP/CS', 't_I + t_L + t_O', '{tI} + {tL} + {tO}', { tI, tL, tO }, control, '5.4'),
      step('machineTime', 't_ME', 't_D + t_R + t_M', '{tD} + {tR} + {tM}', { tD, tR, tM }, machine, '5.4'),
      total,
    ],
    conditions: [],
    messages: [],
  }
}

function measured(inputs: ResponseTimeInputs): ResponseTimeResult {
  const messages: SafetyMessage[] = []
  const conditions: ConditionStats[] = []
  for (const condition of MEASUREMENT_CONDITIONS) {
    const cold = condition === 'cold'
    const stats = conditionStats(condition, cold ? inputs.cold : inputs.warm)
    if (!stats) {
      messages.push({ code: cold ? 'missingSamplesCold' : 'missingSamplesWarm', level: 'warning' })
      continue
    }
    if (stats.n < MIN_SAMPLES) {
      messages.push({
        code: cold ? 'fewSamplesCold' : 'fewSamplesWarm',
        level: 'warning',
        params: { n: stats.n, min: MIN_SAMPLES },
      })
    }
    conditions.push(stats)
  }
  if (conditions.length === 0) {
    return { method: 'measured', t: null, steps: [], conditions, messages: [missing()] }
  }

  const tm = Math.max(...conditions.map((c) => c.t))
  const tF = inputs.tF ?? 0
  const t = tm + tF
  const args: Record<string, number> = {}
  for (const c of conditions) args[c.condition] = c.t
  // The time of each condition is listed with its statistics; T_m is the
  // larger of them (B.2).
  const steps: CalcStep[] = [
    step(
      'measuredTime',
      'T_m',
      null,
      conditions.length === 2 ? 'max({cold}, {warm})' : null,
      args,
      tm,
      'B.5',
    ),
    step('responseTime', 'T', 'T_m + t_F', '{tm} + {tF}', { tm, tF }, t, '5.4', '5'),
  ]
  return { method: 'measured', t, steps, conditions, messages }
}

function missing(): SafetyMessage {
  return { code: 'missingResponseTime', level: 'warning' }
}

/** T after the chosen method: a known value, the sum of equation (3), or measurements after Annex B. */
export function calculateResponseTime(inputs: ResponseTimeInputs): ResponseTimeResult {
  if (inputs.method === 'components') return components(inputs)
  if (inputs.method === 'measured') return measured(inputs)
  return direct(inputs)
}
