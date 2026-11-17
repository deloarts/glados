import {
  blockCell,
  bulletList,
  cell,
  CONTENT_WIDTH,
  dataTable,
  DRAWING_COLORS,
  footnote,
  group,
  keepTogether,
  keyValueGrid,
  labelWithSymbol,
  noteCell,
  notice,
  paragraph,
  REPORT_EMPTY,
  section,
  shareBar,
  span,
  statusChip,
  subheading,
  svgFigure,
  symbol,
  twoColumns,
  withUnit,
} from '@/shared/reports'
import type { Content, KeyValue, ReportContext, ReportTone, ReportTranslate, TableCell } from '@/shared/reports'
import type { ToolReportBody } from '../toolReport'
import { CHART_BOX, CHART_PLOT, chartLayout } from './chart'
import type { ChartReference } from './chart'
import {
  brakeStopText,
  checkRows,
  issueText,
  keyFigures,
  phaseLabel,
  torqueReferences,
  verdictText,
} from './display'
import type { CheckRow } from './display'
import { sizeDrive, speedTrace, torqueTrace } from './engine'
import type { CheckStatus, DriveSizingSuccess } from './engine'
import { useDriveSizingFormat } from './format'
import { decodeDriveSizingInputs } from './inputs'
import { isFieldRelevant, NUMERIC_FIELDS } from './model'
import type { DriveSizingInput, FieldGroup, NumericField } from './model'
import { driveSizingSnapshot } from './snapshot'
import { describeAxis } from './summary'

/**
 * The PDF report of a drive sizing: the settings, the verdict and checks,
 * both charts, the motion profile as entered and the results per segment.
 * It recalculates from the inputs, like the tab, so the report always shows
 * what the current engine gives for them.
 */

type Format = ReturnType<typeof useDriveSizingFormat>

const TONES: Record<CheckStatus, ReportTone> = { pass: 'pass', fail: 'fail', warn: 'warn', info: 'info' }

const CHART_COLORS: Record<ChartReference['tone'], string> = {
  limit: DRAWING_COLORS.limit,
  rated: DRAWING_COLORS.rated,
  mean: DRAWING_COLORS.muted,
}

function fieldValue(field: NumericField, input: DriveSizingInput, t: ReportTranslate, fmt: Format): string {
  const value = input[field.key]
  if (value === null) return field.optional ? t(`tools.driveSizing.placeholders.${field.key}`) : REPORT_EMPTY
  const amount = fmt.num(value, field.digits)
  return field.unit ? `${amount} ${field.unit}` : amount
}

function settingsGroup(group: FieldGroup, input: DriveSizingInput, t: ReportTranslate, fmt: Format): Content {
  const items: KeyValue[] = []
  if (group === 'axis') {
    items.push(
      { label: t('tools.driveSizing.orientation.label'), value: t(`tools.driveSizing.orientation.${input.orientation}`) },
      {
        label: t('tools.driveSizing.transmission.label'),
        value: t(`tools.driveSizing.transmission.${input.transmission}`),
      },
    )
  }
  for (const field of NUMERIC_FIELDS) {
    if (field.group !== group || !isFieldRelevant(field.key, input)) continue
    items.push({
      label: labelWithSymbol(t(`tools.driveSizing.fields.${field.key}`), field.symbol[0], field.symbol[1]),
      value: fieldValue(field, input, t, fmt),
    })
  }
  return keepTogether([subheading(t(`tools.driveSizing.groups.${group}`)), keyValueGrid(items, 1)])
}

function settingsSection(input: DriveSizingInput, t: ReportTranslate, fmt: Format): Content {
  return section(
    t('tools.driveSizing.report.settings'),
    twoColumns(
      group([settingsGroup('axis', input, t, fmt), settingsGroup('gearbox', input, t, fmt)]),
      group([settingsGroup('motor', input, t, fmt), settingsGroup('load', input, t, fmt)]),
    ),
  )
}

function checkCells(row: CheckRow): TableCell[] {
  return [
    noteCell(span(row.name, 'emphasis'), [row.note]),
    cell(row.value, { noWrap: true }),
    cell(row.limitSymbol ? [symbol(row.limitSymbol[0], row.limitSymbol[1]), ` ${row.limit}`] : row.limit, { noWrap: true }),
    row.utilisation === null
      ? ''
      : blockCell([paragraph(row.utilisationText), shareBar(row.utilisation, TONES[row.status])]),
    statusChip(row.statusText, TONES[row.status]),
  ]
}

function resultsSection(
  input: DriveSizingInput,
  result: DriveSizingSuccess,
  t: ReportTranslate,
  fmt: Format,
): Content {
  const rows = checkRows(
    result,
    { brakeSafetyFactor: input.brakeSafetyFactor ?? 0, maxSpeedGiven: input.maxSpeedRpm !== null },
    t,
    fmt,
  )
  const failed = rows.filter((row) => row.status === 'fail').length
  const content: Content[] = [
    notice(verdictText(failed, t), failed === 0 ? 'pass' : 'fail'),
    keyValueGrid(keyFigures(result, fmt).map((figure) => ({ label: t(`tools.driveSizing.figures.${figure.key}`), value: figure.value }))),
    group(
      [
        dataTable(
          [
            { header: t('tools.driveSizing.checks.columns.check'), width: '*' },
            { header: t('tools.driveSizing.checks.columns.value'), align: 'right' },
            { header: t('tools.driveSizing.checks.columns.limit'), align: 'right' },
            { header: t('tools.driveSizing.checks.columns.utilisation'), width: 60, align: 'right' },
            { header: t('tools.driveSizing.checks.columns.status') },
          ],
          rows.map(checkCells),
        ),
      ],
      'before',
    ),
  ]
  const stop = brakeStopText(result.brakeStop, t, fmt)
  if (stop) {
    content.push(
      notice(
        group([paragraph(stop), paragraph(t('tools.driveSizing.brakeStop.note'), 'note')]),
        'info',
        t('tools.driveSizing.brakeStop.title'),
      ),
    )
  }
  if (result.warnings.length > 0) {
    const texts = result.warnings.map((issue) => issueText(issue, t, fmt, result.endPositionMm))
    content.push(notice(bulletList(texts), 'warn', t('tools.driveSizing.issues.warningsTitle')))
  }
  return section(t('tools.driveSizing.report.results'), ...content)
}

function escapeXml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/** A chart as an SVG string with the report's fixed colours and fonts. */
export function chartSvg(
  points: ReadonlyArray<readonly [number, number]>,
  duration: number,
  references: readonly ChartReference[],
  unit: string,
  timeLabel: string,
  fmt: Format,
): string {
  const layout = chartLayout(points, duration, references)
  const { left, top, width, height, bottom } = CHART_BOX
  const right = left + CHART_PLOT.width
  const textAttrs = `font-size="12" fill="${DRAWING_COLORS.muted}"`
  const parts: string[] = []
  for (const tick of layout.yTicks) {
    const y = layout.y(tick).toFixed(1)
    parts.push(`<line x1="${left}" x2="${right}" y1="${y}" y2="${y}" stroke="${DRAWING_COLORS.rule}" stroke-width="1"/>`)
    parts.push(`<text x="${left - 6}" y="${(layout.y(tick) + 4).toFixed(1)}" text-anchor="end" ${textAttrs}>${escapeXml(fmt.num(tick, 2))}</text>`)
  }
  for (const tick of layout.xTicks) {
    const x = layout.x(tick).toFixed(1)
    parts.push(`<line x1="${x}" x2="${x}" y1="${top}" y2="${top + CHART_PLOT.height}" stroke="${DRAWING_COLORS.rule}" stroke-width="1"/>`)
    parts.push(`<text x="${x}" y="${height - bottom + 16}" text-anchor="middle" ${textAttrs}>${escapeXml(fmt.num(tick, 2))}</text>`)
  }
  if (layout.area) {
    parts.push(`<path d="${layout.area}" fill="${DRAWING_COLORS.line}" fill-opacity="0.12"/>`)
  }
  const zero = layout.y(0).toFixed(1)
  parts.push(`<line x1="${left}" x2="${right}" y1="${zero}" y2="${zero}" stroke="${DRAWING_COLORS.ink}" stroke-width="1.5"/>`)
  for (const reference of references) {
    const y = layout.y(reference.value).toFixed(1)
    const dash = reference.tone === 'mean' ? '2 3' : '6 4'
    parts.push(
      `<line x1="${left}" x2="${right}" y1="${y}" y2="${y}" stroke="${CHART_COLORS[reference.tone]}" stroke-width="1.5" stroke-dasharray="${dash}"/>`,
    )
  }
  for (const { reference, y } of layout.labels) {
    const [base, sub] = reference.symbol
    const subscript = sub ? `<tspan dy="3" font-size="10" font-style="normal">${escapeXml(sub)}</tspan>` : ''
    parts.push(
      `<text x="${right + 6}" y="${y.toFixed(1)}" font-size="13" font-style="italic" font-weight="bold" fill="${CHART_COLORS[reference.tone]}">${escapeXml(base)}${subscript}</text>`,
    )
  }
  if (layout.line) {
    parts.push(`<path d="${layout.line}" fill="none" stroke="${DRAWING_COLORS.line}" stroke-width="2" stroke-linejoin="round"/>`)
  }
  parts.push(`<text x="${left - 6}" y="${top - 4}" text-anchor="end" font-weight="bold" ${textAttrs}>${escapeXml(unit)}</text>`)
  parts.push(`<text x="${right}" y="${height - 2}" text-anchor="end" font-weight="bold" ${textAttrs}>${escapeXml(timeLabel)}</text>`)
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" font-family="${DRAWING_COLORS.font}">${parts.join('')}</svg>`
}

function chartsSection(input: DriveSizingInput, result: DriveSizingSuccess, t: ReportTranslate, fmt: Format): Content {
  const timeLabel = t('tools.driveSizing.charts.time')
  const speed = chartSvg(speedTrace(result.segments), result.cycleTimeS, [], t('tools.driveSizing.charts.speedUnit'), timeLabel, fmt)
  const torque = chartSvg(
    torqueTrace(result.segments),
    result.cycleTimeS,
    torqueReferences(result, input.maxTorqueNm ?? 0, input.ratedTorqueNm ?? 0),
    t('tools.driveSizing.charts.torqueUnit'),
    timeLabel,
    fmt,
  )
  return section(
    t('tools.driveSizing.report.charts'),
    svgFigure(t('tools.driveSizing.charts.speedTitle'), speed, CONTENT_WIDTH),
    svgFigure(t('tools.driveSizing.charts.torqueTitle'), torque, CONTENT_WIDTH),
  )
}

function profileSection(
  input: DriveSizingInput,
  result: DriveSizingSuccess | null,
  t: ReportTranslate,
  fmt: Format,
): Content[] {
  if (input.segments.length === 0) return []
  const P = 'tools.driveSizing.profile'
  const rows: TableCell[][] = input.segments.map((segment, index) => {
    const yesNo = t(segment.payload ? 'common.yes' : 'common.no')
    if (segment.kind === 'pause') {
      return [
        String(index + 1),
        t(`${P}.kinds.pause`),
        '',
        '',
        '',
        segment.durationS === null ? REPORT_EMPTY : fmt.num(segment.durationS, 3),
        t(`${P}.holding.${segment.brake ? 'brake' : 'motor'}`),
        yesNo,
      ]
    }
    const duration = result?.segments[index]?.durationS
    return [
      String(index + 1),
      t(`${P}.kinds.move`),
      segment.distanceMm === null ? REPORT_EMPTY : fmt.num(segment.distanceMm, 1),
      segment.startSpeed === null ? REPORT_EMPTY : fmt.num(segment.startSpeed, 3),
      segment.endSpeed === null ? REPORT_EMPTY : fmt.num(segment.endSpeed, 3),
      duration === undefined ? REPORT_EMPTY : cell(fmt.fixed(duration, 3), { style: 'muted' }),
      '',
      yesNo,
    ]
  })
  const hint = input.orientation === 'horizontal' ? `${P}.hintHorizontal` : `${P}.hintVertical`
  return [
    section(
      t(`${P}.title`),
      dataTable(
        [
          { header: t(`${P}.columns.index`), align: 'right' },
          { header: t(`${P}.columns.kind`), width: '*' },
          { header: withUnit(t(`${P}.columns.distance`), 'mm'), align: 'right' },
          { header: withUnit(t(`${P}.columns.startSpeed`), 'm/s'), align: 'right' },
          { header: withUnit(t(`${P}.columns.endSpeed`), 'm/s'), align: 'right' },
          { header: withUnit(t(`${P}.columns.duration`), 's'), align: 'right' },
          { header: t(`${P}.columns.holding`) },
          { header: t(`${P}.columns.payload`) },
        ],
        rows,
      ),
      footnote(t(hint)),
    ),
  ]
}

function segmentsSection(input: DriveSizingInput, result: DriveSizingSuccess, t: ReportTranslate, fmt: Format): Content {
  const S = 'tools.driveSizing.segments'
  const maxTorque = input.maxTorqueNm ?? Number.POSITIVE_INFINITY
  const rows: TableCell[][] = result.segments.map((segment) => {
    const phase = phaseLabel(segment, input.orientation, t)
    const position =
      segment.kind === 'move'
        ? `${fmt.fixed(segment.startMm, 0)} → ${fmt.fixed(segment.endMm, 0)}`
        : fmt.fixed(segment.startMm, 0)
    return [
      String(segment.index + 1),
      segment.regenerative
        ? cell([phase, span(` (${t(`${S}.regenerative`)})`, 'muted')])
        : phase,
      fmt.num(segment.massKg, 2),
      cell(position, { noWrap: true, ...(segment.outOfStroke ? { style: 'alert' as const } : {}) }),
      fmt.fixed(segment.durationS, 3),
      fmt.fixed(segment.accelerationMs2, 3),
      fmt.fixed(segment.forceN, 1),
      fmt.fixed(segment.speedRpm, 0),
      Math.abs(segment.torqueNm) > maxTorque
        ? cell(fmt.fixed(segment.torqueNm, 2), { style: 'alert' })
        : fmt.fixed(segment.torqueNm, 2),
    ]
  })
  return section(
    t(`${S}.title`),
    dataTable(
      [
        { header: t(`${S}.columns.index`), align: 'right' },
        { header: t(`${S}.columns.phase`), width: '*' },
        { header: withUnit(t(`${S}.columns.mass`), 'kg'), align: 'right' },
        { header: withUnit(t(`${S}.columns.position`), 'mm'), align: 'right' },
        { header: withUnit(t(`${S}.columns.time`), 's'), align: 'right' },
        { header: withUnit(t(`${S}.columns.acceleration`), 'm/s²'), align: 'right' },
        { header: withUnit(t(`${S}.columns.force`), 'N'), align: 'right' },
        { header: withUnit(t(`${S}.columns.speed`), 'rpm'), align: 'right' },
        { header: withUnit(t(`${S}.columns.torque`), 'Nm'), align: 'right' },
      ],
      rows,
    ),
    footnote(t(`${S}.note`)),
  )
}

export function driveSizingReport(inputs: Record<string, unknown>, { t, locale }: ReportContext): ToolReportBody {
  const fmt = useDriveSizingFormat(locale)
  const { input } = decodeDriveSizingInputs(inputs)
  const result = sizeDrive(input)
  const subtitle = describeAxis(
    {
      orientation: input.orientation,
      angleDeg: input.orientation === 'inclined' ? input.angleDeg : null,
      ratio: input.ratio,
      carriageMassKg: input.carriageMassKg,
      payloadMassKg: input.payloadMassKg,
    },
    t,
    fmt,
  )
  const body: Content[] = []
  if (result.ok) {
    body.push(
      resultsSection(input, result, t, fmt),
      settingsSection(input, t, fmt),
      chartsSection(input, result, t, fmt),
      ...profileSection(input, result, t, fmt),
      segmentsSection(input, result, t, fmt),
    )
  } else {
    const errors = result.errors.map((issue) => issueText(issue, t, fmt))
    body.push(
      notice(bulletList(errors), 'warn', t('tools.driveSizing.issues.errorsTitle')),
      settingsSection(input, t, fmt),
      ...profileSection(input, null, t, fmt),
    )
  }
  return { subtitle, body, results: driveSizingSnapshot(input, result) }
}
