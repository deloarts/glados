import { finiteNumberOrNull, isPlainRecord } from '@/core/utils/guards'
import { useDriveSizingFormat } from './format'
import { ORIENTATIONS } from './model'
import type { Orientation } from './model'
import type { Translate } from '@/core/i18n'

/** The inputs that name a drive sizing, as the results snapshot repeats them. */
export interface AxisSetup {
  orientation: Orientation
  angleDeg: number | null
  ratio: number | null
  carriageMassKg: number | null
  payloadMassKg: number | null
}

function readSetup(value: unknown): AxisSetup | null {
  if (!isPlainRecord(value)) return null
  const orientation = value.orientation
  const known = typeof orientation === 'string' && (ORIENTATIONS as readonly string[]).includes(orientation)
  if (!known) return null
  return {
    orientation: orientation as Orientation,
    angleDeg: finiteNumberOrNull(value.angleDeg),
    ratio: finiteNumberOrNull(value.ratio),
    carriageMassKg: finiteNumberOrNull(value.carriageMassKg),
    payloadMassKg: finiteNumberOrNull(value.payloadMassKg),
  }
}

function readCheck(value: unknown): { value: number; utilisationPct: number } | null {
  if (!isPlainRecord(value)) return null
  const amount = finiteNumberOrNull(value.value)
  const utilisationPct = finiteNumberOrNull(value.utilisationPct)
  return amount === null || utilisationPct === null ? null : { value: amount, utilisationPct }
}

/**
 * "Vertical axis, 140 kg, i = 12": the orientation, the loaded mass and the
 * gearbox ratio. Without mass and ratio the axis is not described yet, which
 * is a cleared form, and it is called a new drive sizing instead.
 */
export function describeAxis(
  setup: AxisSetup,
  t: Translate,
  fmt: ReturnType<typeof useDriveSizingFormat> = useDriveSizingFormat(),
): string {
  const { num } = fmt
  const hasMass = setup.carriageMassKg !== null && setup.payloadMassKg !== null
  if (!hasMass && setup.ratio === null) return t('tools.driveSizing.newTitle')
  let axis = t(`tools.driveSizing.axisTitle.${setup.orientation}`)
  if (setup.orientation === 'inclined' && setup.angleDeg !== null) {
    axis += ` (${num(setup.angleDeg, 2)}°)`
  }
  const parts = [axis]
  if (hasMass) parts.push(`${num((setup.carriageMassKg ?? 0) + (setup.payloadMassKg ?? 0), 2)} kg`)
  if (setup.ratio !== null) parts.push(`i = ${num(setup.ratio, 3)}`)
  return parts.join(', ')
}

/**
 * One line for lists of saved calculations: the axis, peak and RMS torque
 * with their utilisation, and whether every check passed. Returns an empty
 * string for results that do not have the shape the drive sizing saves.
 */
export function summarizeDriveSizing(results: Record<string, unknown>, t: Translate): string {
  if (!isPlainRecord(results)) return ''
  const setup = readSetup(results.setup)
  if (!setup) return ''
  const axis = describeAxis(setup, t)
  if (results.ok === false) return t('tools.driveSizing.summary.invalid', { axis })
  if (results.ok !== true || !isPlainRecord(results.checks)) return ''

  const peak = readCheck(results.checks.peakTorque)
  const rms = readCheck(results.checks.rmsTorque)
  const failed = finiteNumberOrNull(results.failedChecks)
  if (!peak || !rms || failed === null) return ''

  const { fixed, percent } = useDriveSizingFormat()
  const verdict =
    failed === 0
      ? t('tools.driveSizing.summary.allPassed')
      : failed === 1
        ? t('tools.driveSizing.summary.oneFailed')
        : t('tools.driveSizing.summary.manyFailed', { count: failed })
  return t('tools.driveSizing.summary.line', {
    axis,
    peak: fixed(peak.value, 2),
    peakShare: percent(peak.utilisationPct / 100),
    rms: fixed(rms.value, 2),
    rmsShare: percent(rms.utilisationPct / 100),
    verdict,
  })
}
