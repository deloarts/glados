import {
  blockCell,
  cell,
  dataTable,
  group,
  keyValueGrid,
  notice,
  orDash,
  paragraph,
  REPORT_EMPTY,
  section,
  statusChip,
  subheading,
} from '@/shared/reports'
import { documentReference, documentReportNotice } from '@/shared/documents'
import type { Content, KeyValue, ReportContext, ReportSpec, ReportTone, TableCell } from '@/shared/reports'
import type { ChecklistResponse } from '../types/checklist'
import {
  CHECKLISTS,
  itemHintKey,
  itemTextKey,
  partTitleKey,
  sectionTitleKey,
  typeLabelKey,
} from './definitions'
import type { Problem, Verdict } from './evaluation'
import { checklistStatus, ownerOf } from './owner'
import { formatReferences } from './references'
import { answersFromRecord, headerFromRecord } from './state'
import { checklistResults } from './summary'
import { ANSWERS, isChecklistType } from './types'
import type { Answer, ChecklistDefinition, ChecklistHeader, ChecklistItem, ChecklistState } from './types'

/**
 * The PDF report of one checklist revision, for documentation: what the
 * checklist page shows, nothing added. It is driven only by the checklist's
 * definition, so every checklist type is reported the same way and a new
 * type needs no report code. The item hints are an option, since they make
 * the report much longer.
 */

const C = 'checklists'

const ANSWER_TONES: Record<Answer, ReportTone> = { yes: 'pass', na: 'info', no: 'fail', defect: 'fail' }
const VERDICT_TONES: Record<Verdict, ReportTone> = { passed: 'pass', open: 'warn', failed: 'fail' }

function details(checklist: ChecklistResponse, { t, dateTime }: ReportContext): KeyValue[] {
  const owner = ownerOf(checklist)
  const status = (() => {
    switch (checklistStatus(checklist)) {
      case 'released':
        return t(`${C}.status.releasedBy`, {
          name: checklist.released_by_full_name ?? '',
          date: dateTime(checklist.released_at ?? ''),
        })
      case 'superseded':
        return t(`${C}.status.supersededOn`, { date: dateTime(checklist.superseded_at ?? '') })
      case 'done':
        return t(`${C}.status.done`)
      default:
        return t(`${C}.report.draft`)
    }
  })()
  const reference = documentReference(checklist, t)
  const revision = checklist.revision_reason ? `${reference}, ${checklist.revision_reason}` : reference
  return [
    {
      label: t(`${C}.report.owner`),
      value: owner.kind === 'personal' ? t(`${C}.owner.personal`) : `${t(`${C}.owner.${owner.kind}`)} ${owner.label}`,
    },
    { label: t(`${C}.report.status`), value: status },
    { label: t(`${C}.report.revision`), value: revision },
    { label: t(`${C}.report.createdBy`), value: `${checklist.creator_full_name}, ${dateTime(checklist.created)}` },
  ]
}

/** The checklist data as the page lists it, empty fields as a dash. */
function headerSection(checklist: ChecklistResponse, header: ChecklistHeader, verdict: Verdict, context: ReportContext): Content {
  const { t, date, dateTime } = context
  const H = `${C}.header`
  const owner = ownerOf(checklist)
  const ownerRows: KeyValue[] =
    owner.kind === 'personal'
      ? []
      : [
          { label: t(`${H}.owner.${owner.kind}`), value: orDash(header.ownerNumber) },
          { label: t(`${H}.owner.customer`), value: orDash(header.ownerCustomer) },
          ...(owner.kind === 'project' ? [{ label: t(`${H}.owner.product`), value: orDash(header.ownerProduct) }] : []),
          { label: t(`${H}.owner.manager`), value: orDash(header.ownerManager) },
        ]
  const machineRows: KeyValue[] = [
    ...(['designation', 'machineType', 'installationSite', 'installationLocation'] as const).map((field) => ({
      label: t(`${H}.${field}`),
      value: orDash(header[field]),
    })),
    { label: t(`${H}.placingOnMarket`), value: header.placingOnMarket ? date(header.placingOnMarket) : REPORT_EMPTY },
    { label: t(`${H}.legalBasis`), value: t(`${C}.legalBases.${header.legalBasis}`) },
  ]
  const confirmationRows: KeyValue[] = [
    { label: t(`${H}.assessedBy`), value: orDash(header.assessedBy) },
    { label: t(`${H}.assessedOn`), value: header.assessedOn ? date(header.assessedOn) : REPORT_EMPTY },
    {
      label: t(`${H}.checkedBy`),
      value: checklist.released_at
        ? `${checklist.released_by_full_name ?? ''}, ${dateTime(checklist.released_at)}`
        : t(`${H}.notReleased`),
    },
    { label: t(`${C}.summaryCard.title`), value: t(`${C}.verdicts.${verdict}`) },
  ]
  return section(
    t(`${H}.title`),
    ownerRows.length > 0 ? keyValueGrid(ownerRows) : paragraph(t(`${H}.owner.personal`), 'muted'),
    keyValueGrid(machineRows, 2, 'before'),
    subheading(t(`${H}.confirmationTitle`)),
    paragraph(t(`${H}.confirmation`), undefined, 'tight'),
    keyValueGrid(confirmationRows),
    keyValueGrid(
      [
        { label: t(`${H}.reason`), value: orDash(header.reason) },
        { label: t(`${H}.notes`), value: orDash(header.notes) },
      ],
      1,
      'before',
    ),
  )
}

function answerCell(answer: Answer | undefined, t: ReportContext['t']): TableCell {
  return answer === undefined ? cell(REPORT_EMPTY, { style: 'faint' }) : statusChip(t(`${C}.answers.${answer}`), ANSWER_TONES[answer])
}

function findingsTable(definition: ChecklistDefinition, problems: readonly Problem[], t: ReportContext['t']): Content {
  return dataTable(
    [
      { header: t(`${C}.report.position`) },
      { header: t(`${C}.report.requirement`), width: '*' },
      { header: t(`${C}.report.answer`) },
      { header: t(`${C}.remark`), width: 150 },
    ],
    problems.map((problem) => {
      const item = definition.itemById.get(problem.id)
      return [
        cell(problem.position, { noWrap: true }),
        item ? t(itemTextKey(definition.type, item)) : problem.id,
        answerCell(problem.answer, t),
        problem.remark || REPORT_EMPTY,
      ]
    }),
  )
}

function resultSection(definition: ChecklistDefinition, state: ChecklistState, { t }: ReportContext): Content {
  const results = checklistResults(definition, state)
  const S = `${C}.summaryCard`
  const counts: KeyValue[] = [
    ...ANSWERS.map((answer) => ({ label: t(`${C}.answers.${answer}`), value: String(results.counts[answer]) })),
    { label: t(`${S}.open`), value: String(results.counts.open) },
  ]
  return section(
    t(`${S}.title`),
    notice(
      `${t(`${S}.completion`, { percent: results.completion })}. ${t(`${C}.verdictHints.${results.verdict}`)}`,
      VERDICT_TONES[results.verdict],
      t(`${C}.verdicts.${results.verdict}`),
    ),
    keyValueGrid(counts),
    subheading(t(`${S}.problems`)),
    results.problems.length > 0
      ? findingsTable(definition, results.problems, t)
      : paragraph(t(`${S}.noProblems`), 'muted'),
  )
}

function requirementCell(definition: ChecklistDefinition, item: ChecklistItem, state: ChecklistState, context: ReportContext): TableCell {
  const { t, options } = context
  const lines: Content[] = [paragraph(t(itemTextKey(definition.type, item)))]
  const meta = (text: string): Content => paragraph(text, 'note')
  if (item.hint && options.hints) lines.push(paragraph(t(itemHintKey(definition.type, item)), 'hint'))
  const references = formatReferences(item.refs, state.header.legalBasis, t)
  if (references.length > 0) lines.push(meta(references.join('; ')))
  const see = item.see.flatMap((id) => {
    const target = definition.itemById.get(id)
    const targetSection = target && definition.sectionByKey.get(target.sectionKey)
    return target && targetSection ? [t(`${C}.itemReference`, { section: targetSection.number, item: target.number })] : []
  })
  if (see.length > 0) lines.push(meta(t(`${C}.see`, { items: see.join('; ') })))
  if (item.methods.length > 0) {
    lines.push(meta(`${t(`${C}.methodsLabel`)}: ${item.methods.map((m) => `${m} ${t(`${C}.methods.${m}`)}`).join(', ')}`))
  }
  return blockCell(lines, { indent: item.level === 1 })
}

function partSections(definition: ChecklistDefinition, state: ChecklistState, context: ReportContext): Content[] {
  const { t } = context
  return definition.parts.map((part) =>
    section(
      `${part.number} ${t(partTitleKey(definition.type, part.key))}`,
      ...part.sections.map((sec): Content =>
        group(
          [
          subheading(`${sec.number} ${t(sectionTitleKey(definition.type, sec.key))}`),
          dataTable(
            [
              { header: t(`${C}.report.number`), align: 'right' },
              { header: t(`${C}.report.requirement`), width: '*' },
              { header: t(`${C}.report.answer`) },
              { header: t(`${C}.remark`), width: 150 },
            ],
            sec.items.map((item) => [
              cell(item.number, { noWrap: true }),
              requirementCell(definition, item, state, context),
              answerCell(state.answers[item.id], t),
              state.remarks[item.id] || '',
            ]),
          ),
          ],
          'after',
        ),
      ),
    ),
  )
}

/** The report of one checklist revision; null for a type this app does not know. */
export function checklistReportSpec(checklist: ChecklistResponse): ReportSpec | null {
  if (!isChecklistType(checklist.type)) return null
  const definition = CHECKLISTS[checklist.type]
  const read = answersFromRecord(definition, checklist.answers, checklist.remarks)
  const state: ChecklistState = { header: headerFromRecord(checklist.header), answers: read.answers, remarks: read.remarks }
  return {
    title: checklist.title,
    options: [{ key: 'hints', labelKey: `${C}.report.hintsOption` }],
    printTarget: { document: 'checklist_report', rootPublicId: checklist.public_id },
    build: (context) => ({
      kind: context.t(typeLabelKey(definition.type)),
      title: checklist.title,
      details: details(checklist, context),
      notice: documentReportNotice(checklist, context.t, context.dateTime),
      identity: {
        publicId: checklist.public_id,
        reference: documentReference(checklist, context.t),
      },
      body: [
        resultSection(definition, state, context),
        headerSection(checklist, state.header, checklistResults(definition, state).verdict, context),
        ...partSections(definition, state, context),
      ],
    }),
  }
}

