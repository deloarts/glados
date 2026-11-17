import {
  bulletList,
  footnote,
  keepTogether,
  keyValueGrid,
  notice,
  paragraph,
  section,
  span,
} from '@/shared/reports'
import type { Content, KeyValue, ReportTranslate } from '@/shared/reports'
import { formatDistance, formatQuantity, formatRef, messageText } from './format'
import type { SafetyDistanceFormat } from './format'
import { P, rich } from './reportText'
import { modeGroup, STANDARDS } from './types'
import type { SafetyDistanceInputs, SafetyDistanceResult, StandardId, StandardRef } from './types'

/** The result of the Safety Distance report, and its closing with the standards applied. */

export function resultSection(inputs: SafetyDistanceInputs, result: SafetyDistanceResult, f: SafetyDistanceFormat): Content {
  const { t } = f
  const group = modeGroup(inputs.mode)
  const failed = result.messages.some((m) => m.level === 'error')
  const value: Content =
    result.s !== null
      ? paragraph([rich(result.symbol), ` = ${formatDistance(result.s, f)}`], 'value')
      : paragraph(t(`${P}.result.${failed ? 'notPermitted' : 'none'}`), 'valueMissing')
  const content: Content[] = [
    keyValueGrid(
      [
        { label: t(`${P}.groupLabel`), value: t(`${P}.groups.${group}`) },
        { label: t(`${P}.modeLabels.${group === 'reach' ? 'reach' : 'devices'}`), value: t(`${P}.modes.${inputs.mode}`) },
      ],
      1,
    ),
    paragraph(t(`${P}.modeDescriptions.${inputs.mode}`), 'footnote', 'after'),
    value,
    paragraph(
      [
        ...(result.formula ? [rich(result.formula), '     '] : []),
        span(formatRef(result.ref, f, true), 'muted'),
      ],
      undefined,
      'tight',
    ),
  ]

  const figures: KeyValue[] = []
  if (result.k !== null) figures.push({ label: `${t(`${P}.result.approachSpeed`)} K`, value: formatQuantity(result.k, 'mm/s', f) })
  if (result.t !== null) figures.push({ label: `${t(`${P}.result.responseTime`)} T`, value: formatQuantity(result.t, 's', f) })
  if (result.supplement !== null && result.s !== null) {
    figures.push({ label: `${t(`${P}.result.supplement`)} Z`, value: formatQuantity(result.supplement, 'mm', f) })
  }
  if (figures.length > 0) content.push(keyValueGrid(figures, figures.length > 1 ? 2 : 1))
  if (result.s !== null && group === 'devices') content.push(footnote(t(`${P}.result.roundedUp`)))

  for (const level of ['error', 'warning'] as const) {
    for (const message of result.messages.filter((m) => m.level === level)) {
      content.push(notice(rich(messageText(message, f)), level === 'error' ? 'fail' : 'warn'))
    }
  }
  const notes = result.messages.filter((m) => m.level === 'info').map((m) => messageText(m, f))
  if (notes.length > 0) content.push(notice(bulletList(notes), 'info'))
  return section(t(`${P}.result.titles.${group}`), ...content)
}

/** Every standard a reference of the result points to, in the tool's order. */
function standardsUsed(result: SafetyDistanceResult): string[] {
  const refs: StandardRef[] = [
    result.ref,
    ...result.steps.flatMap((step) => (step.ref ? [step.ref] : [])),
    ...result.responseTime.steps.flatMap((step) => (step.ref ? [step.ref] : [])),
    ...result.paths.map((path) => path.ref),
  ]
  const used = new Set<StandardId>(refs.map((ref) => ref.standard ?? 'iso13855'))
  return (Object.keys(STANDARDS) as StandardId[]).filter((id) => used.has(id)).map((id) => STANDARDS[id])
}

/** The standards and the disclaimer, kept on one page. */
export function closingSection(inputs: SafetyDistanceInputs, result: SafetyDistanceResult, t: ReportTranslate): Content {
  return section(
    t(`${P}.report.standards`),
    keepTogether([
      paragraph(standardsUsed(result).join(', ')),
      notice(t(`${P}.result.disclaimers.${modeGroup(inputs.mode)}`), 'info'),
    ]),
  )
}
