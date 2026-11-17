import { documentReference, documentReportNotice, revisionLabel } from '@/shared/documents'
import type { Content, KeyValue, ReportContext, ReportSpec } from '@/shared/reports'
import type { ToolDefinition } from '../registry'
import type { CalculationResponse } from '../types/calculation'
import { resultDifferences } from './calculationCompare'

/**
 * The PDF report of a tool calculation. A tool contributes its body through
 * the registry's `report` loader; this adds what every calculation report
 * shows above it: the calculation's owner, status, author, reference and
 * note, or that it is not saved.
 */

export interface ToolReportBody {
  /** One line under the title describing the inputs, such as "Vertical axis, 140 kg, i = 12". */
  subtitle: string
  body: Content[]
  /** The results recalculated for the report, compared with the saved ones. */
  results: Record<string, unknown>
}

/** Builds a tool's report body from its inputs; it may wait for drawings to render. */
export type ToolReportBuilder = (
  inputs: Record<string, unknown>,
  context: ReportContext,
) => ToolReportBody | Promise<ToolReportBody>

function details(calculation: CalculationResponse | null, { t, dateTime }: ReportContext): KeyValue[] {
  const R = 'tools.calculations.report'
  if (!calculation) return [{ label: t(`${R}.status`), value: t(`${R}.notSaved`) }]
  let owner = t('tools.calculations.owner.personal')
  if (calculation.project_number) owner = `${t('tools.calculations.owner.project')} ${calculation.project_number}`
  else if (calculation.product_number) owner = `${t('tools.calculations.owner.product')} ${calculation.product_number}`
  const status = calculation.released_at
    ? t('tools.calculations.status.releasedBy', {
        name: calculation.released_by_full_name ?? '',
        date: dateTime(calculation.released_at),
      })
    : t(`${R}.draft`)
  const items: KeyValue[] = [
    { label: t(`${R}.owner`), value: owner },
    { label: t(`${R}.status`), value: status },
    { label: t(`${R}.revision`), value: revisionLabel(calculation, t) },
    { label: t(`${R}.createdBy`), value: `${calculation.creator_full_name}, ${dateTime(calculation.created)}` },
    {
      label: t(`${R}.reference`),
      value: t(`${R}.referenceValue`, {
        reference: documentReference(calculation, t),
        version: calculation.engine_version,
      }),
    },
  ]
  if (calculation.note) items.push({ label: t(`${R}.note`), value: calculation.note })
  return items
}

/**
 * The report of a saved calculation, or of the unsaved inputs of the open
 * tool, which can be downloaded but not printed. Null for a tool without a
 * report.
 */
export function toolReportSpec(
  tool: ToolDefinition,
  calculation: CalculationResponse | null,
  draft: { inputs: Record<string, unknown>; title: string } = { inputs: {}, title: '' },
): ReportSpec | null {
  const loader = tool.report
  if (!loader) return null
  const inputs = calculation ? (calculation.inputs as Record<string, unknown>) : draft.inputs
  return {
    title: calculation?.title ?? draft.title,
    options: tool.reportOptions ?? [],
    printTarget: calculation ? { document: 'calculation_report', rootPublicId: calculation.public_id } : null,
    engineVersion: tool.engineVersion,
    build: async (context) => {
      const builder = await loader()
      const report = await builder(inputs, context)
      // The report recalculates from the stored inputs; when today's engine
      // gives other results than the saved record holds, the reader is told.
      const mismatch = calculation !== null && resultDifferences(calculation.results, report.results).length > 0
      return {
        kind: context.t(tool.labelKey),
        title: calculation?.title ?? report.subtitle,
        subtitle: report.subtitle,
        details: details(calculation, context),
        notice:
          (calculation && documentReportNotice(calculation, context.t, context.dateTime)) ??
          (mismatch ? { text: context.t('tools.calculations.report.mismatch'), tone: 'warn' } : null),
        identity: calculation
          ? {
              publicId: calculation.public_id,
              reference: documentReference(calculation, context.t),
            }
          : null,
        body: report.body,
      }
    },
  }
}
