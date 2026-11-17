import { blockCell, cell, dataTable, footnote, paragraph, section, span, subheading } from '@/shared/reports'
import type { Content, Inline, TableCell } from '@/shared/reports'
import { fillExpression, formatQuantity, formatRef, messageText } from './format'
import type { SafetyDistanceFormat } from './format'
import { P, quantity, rich, strong } from './reportText'
import type { SafetyDistanceResult } from './types'

/** The worked calculation of the Safety Distance report, step by step, and the approach paths. */

function stepRow(step: SafetyDistanceResult['steps'][number], f: SafetyDistanceFormat): TableCell[] {
  const line: Inline[] = [rich(step.symbol)]
  if (step.formula) line.push(' = ', rich(step.formula))
  const expression = fillExpression(step, f)
  if (expression) line.push(` = ${expression}`)
  line.push(' = ', strong(formatQuantity(step.value, step.unit, f)))
  const blocks: Content[] = [paragraph(line)]
  if (step.note) blocks.push(paragraph(rich(messageText(step.note, f)), 'note'))
  return [f.t(`${P}.steps.${step.key}`), blockCell(blocks), cell(step.ref ? formatRef(step.ref, f) : '', { style: 'muted' })]
}

export function calculationSection(result: SafetyDistanceResult, f: SafetyDistanceFormat): Content {
  const { t } = f
  const steps = [...result.responseTime.steps, ...result.steps]
  if (steps.length === 0) return section(t(`${P}.sections.calculation`), paragraph(t(`${P}.steps.empty`), 'muted'))
  const content: Content[] = [
    dataTable(
      [
        { header: t(`${P}.steps.columns.quantity`), width: 120 },
        { header: t(`${P}.steps.columns.calculation`), width: '*' },
        { header: t(`${P}.steps.columns.source`), width: 110 },
      ],
      steps.map((step) => stepRow(step, f)),
    ),
  ]
  if (result.paths.length > 0) {
    content.push(
      subheading(t(`${P}.paths.title`)),
      dataTable(
        [
          { header: t(`${P}.paths.columns.path`), width: '*' },
          { header: t(`${P}.paths.columns.reach`), align: 'right' },
          { header: 'K', align: 'right' },
          { header: 'S', align: 'right' },
          { header: t(`${P}.steps.columns.source`) },
        ],
        result.paths.map((p) => [
          t(`${P}.paths.${p.path}`),
          quantity(p.reach, 'mm', f),
          quantity(p.k, 'mm/s', f),
          p.s === null ? t(`${P}.paths.notCovered`) : cell(span(formatQuantity(p.s, 'mm', f), 'emphasis')),
          cell(formatRef(p.ref, f), { style: 'muted' }),
        ]),
      ),
      footnote(t(`${P}.paths.hint`)),
    )
  }
  return section(t(`${P}.sections.calculation`), ...content)
}
