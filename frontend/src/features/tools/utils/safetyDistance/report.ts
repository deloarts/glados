import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { drawing, section } from '@/shared/reports'
import type { Content, ReportContext } from '@/shared/reports'
import type { ToolReportBody } from '../toolReport'
import { calculateSafetyDistance, safetyDistanceSnapshot, usesResponseTime } from './calculate'
import { numberOptions } from './format'
import type { SafetyDistanceFormat } from './format'
import { decodeSafetyDistanceInputs } from './inputRecord'
import { appendixSection } from './reportAppendix'
import { calculationSection } from './reportCalculation'
import { inputsSection, responseTimeSection } from './reportInputs'
import { closingSection, resultSection } from './reportResult'
import { renderSafetyDistanceSketches } from './reportSketches'
import { P } from './reportText'
import { summarizeSafetyDistance } from './summary'

/**
 * The PDF report of a safety distance, written as a calculation record for a
 * machine's technical file: the result with its formula and source, the
 * inputs of the chosen mode, the response time, the worked calculation, the
 * tab's sketches, the standards applied with the disclaimer and, when asked
 * for, the reference tables as an appendix. It recalculates from the inputs,
 * like the tab. Who released the calculation and when is in the report's
 * details, since sign-off happens in the app and not on paper.
 */
export async function safetyDistanceReport(
  record: Record<string, unknown>,
  { t, locale, options }: ReportContext,
): Promise<ToolReportBody> {
  const { formatNumber } = useLocaleFormat(locale)
  const f: SafetyDistanceFormat = { t, number: (value, digits) => formatNumber(value, numberOptions(digits)) }
  const fixed = (value: number, digits: number) => formatNumber(value, numberOptions(digits, true))
  const { inputs } = decodeSafetyDistanceInputs(record)
  const result = calculateSafetyDistance(inputs)
  const snapshot = safetyDistanceSnapshot(inputs, result)
  const sketches = await renderSafetyDistanceSketches(inputs, result, locale)

  const body: Content[] = [resultSection(inputs, result, f), inputsSection(inputs, f)]
  if (usesResponseTime(inputs)) body.push(responseTimeSection(inputs, result, f))
  body.push(calculationSection(result, f))
  if (sketches.length > 0) {
    body.push(section(t(`${P}.report.sketches`), ...sketches.map((sketch) => drawing(sketch.svg, sketch.caption))))
  }
  body.push(closingSection(inputs, result, t))
  if (options.appendix) body.push(...appendixSection(inputs, t, fixed))

  return { subtitle: summarizeSafetyDistance(snapshot, t), body, results: snapshot }
}
