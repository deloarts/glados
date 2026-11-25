import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { useMadeItemLabel } from '@/features/made-items'
import {
  cell,
  dataTable,
  footnote,
  group,
  keepTogether,
  keyValueGrid,
  noteCell,
  orDash,
  paragraph,
  picture,
  REPORT_EMPTY,
  section,
  statusChip,
  subheading,
  twoColumns,
} from '@/shared/reports'
import type { Content, KeyValue, ReportContext, ReportSpec, ReportTone, TableCell } from '@/shared/reports'
import type { LotPositionResponse, LotResponse, LotStepResponse } from '../../types/productionLotsResponse'
import type { ProductionOrderCompletionResponse, ProductionOrderResponse } from '../../types/productionOrdersResponse'
import { lotPositionStatusKey } from '../../utils/lotStatus'
import { lotEventLabelKey } from './lotEventLabels'
import { loadInspectionReportData } from './inspectionReportData'
import type { InspectionReportData } from './inspectionReportData'
import { bySequence, sortedBySequence } from '../../utils/sequence'
import { localizeLabel } from '@/shared/utils/localizeLabel'

/**
 * The inspection report of a production lot, for the customer or the
 * quality file: what was made from what, every inspection with its results,
 * reasons and evidence, the goods receipt of external processing, the
 * nonconformities and the follow-up lots they led to, and the quality
 * history. It shows only what Glados holds, in the state of the lot on the
 * day it is exported, so a lot that is not completed carries a warning.
 */

const R = 'production.lots.report'

type Translate = ReportContext['t']

interface Format {
  t: Translate
  n: (value: number) => string
  dateTime: (value: string) => string
  date: (value: string) => string
}

const ACTIVE_TONE: Record<string, ReportTone> = {
  completed: 'pass',
  canceled: 'fail',
  scrapped: 'fail',
}

function byAt(name: string | null | undefined, at: string | null | undefined, f: Format): string {
  if (!at) return orDash(name)
  return name ? f.t(`${R}.byAt`, { name, date: f.dateTime(at) }) : f.dateTime(at)
}

function reason(value: string | null | undefined, t: Translate): string {
  return value ? t(`production.scrap.reasons.${value}`) : REPORT_EMPTY
}

function inspectionStepOf(position: LotPositionResponse): LotStepResponse | null {
  return (position.steps ?? []).find((step) => step.role === 'inspection') ?? null
}

function methodOf(step: LotStepResponse): string {
  return localizeLabel(
    step.role === 'inspection' ? step.inspection_method_name : step.fabrication_method_name,
  )
}

function ordersOf(data: InspectionReportData, position: LotPositionResponse): ProductionOrderResponse[] {
  return data.productionOrders
    .filter((order) => order.lot_position_id === position.id)
    .sort((a, b) => a.production_order_number.localeCompare(b.production_order_number))
}

function completionsOf(order: ProductionOrderResponse): ProductionOrderCompletionResponse[] {
  return [...(order.completions ?? [])].sort((a, b) => a.created.localeCompare(b.created))
}

function sum(values: number[]): number {
  return values.reduce((total, value) => total + value, 0)
}

// ── Details ──────────────────────────────────────────────────────────

function details(lot: LotResponse, f: Format): KeyValue[] {
  const { t } = f
  const items: KeyValue[] = [
    {
      label: t(`${R}.project`),
      value: [lot.project_number, lot.project_customer].filter(Boolean).join(', ') || REPORT_EMPTY,
    },
    { label: t(`${R}.status`), value: t(`production.lots.status.${lot.status}`) },
    {
      label: t(`${R}.quantity`),
      value: t(`${R}.quantityValue`, {
        quantity: f.n(lot.quantity),
        completed: f.n(lot.quantity_completed),
        scrapped: f.n(lot.quantity_scrapped ?? 0),
      }),
    },
    { label: t(`${R}.createdBy`), value: byAt(lot.creator?.full_name, lot.created, f) },
    { label: t(`${R}.due`), value: lot.required_delivery_date ? f.date(lot.required_delivery_date) : REPORT_EMPTY },
  ]
  if (lot.completed_at) items.push({ label: t(`${R}.completed`), value: f.dateTime(lot.completed_at) })
  if (lot.origin_lot_number && lot.origin_disposition) {
    items.push({
      label: t(`${R}.origin`),
      value: t(`${R}.originValue`, {
        lot: lot.origin_lot_number,
        disposition: t(`${R}.dispositions.${lot.origin_disposition}`),
      }),
    })
  }
  if (lot.note) items.push({ label: t(`${R}.note`), value: lot.note })
  return items
}

function statusNotice(lot: LotResponse, f: Format): { text: string; tone: ReportTone } | null {
  if (lot.status === 'completed') return null
  const tone = ACTIVE_TONE[lot.status] ?? 'warn'
  return {
    tone,
    text: f.t(`${R}.notCompleted`, { status: f.t(`production.lots.status.${lot.status}`) }),
  }
}

// ── Summary ──────────────────────────────────────────────────────────

function inspectionPositions(lot: LotResponse): LotPositionResponse[] {
  return [...(lot.positions ?? [])]
    .filter((position) => inspectionStepOf(position) !== null)
    .sort(bySequence)
}

function receiptRejected(data: InspectionReportData): number {
  return sum(
    [...data.ordersById.values()].flatMap((order) =>
      order.items
        .filter((item) => item.lot_id === data.lot.id)
        .flatMap((item) => (item.delivery_records ?? []).map((record) => record.quantity_rejected ?? 0)),
    ),
  )
}

function summarySection(data: InspectionReportData, f: Format): Content {
  const { t } = f
  const lot = data.lot
  const rows: TableCell[][] = inspectionPositions(lot).map((position) => {
    const completions = ordersOf(data, position).flatMap(completionsOf)
    const step = inspectionStepOf(position)!
    return [
      cell(String(position.sequence), { align: 'right' }),
      methodOf(step),
      f.n(sum(completions.map((c) => c.quantity))),
      f.n(sum(completions.map((c) => c.quantity_accepted))),
      f.n(sum(completions.map((c) => c.quantity_rejected))),
      statusChip(
        t(`production.lots.positionStatus.${lotPositionStatusKey(position.status, position.kind)}`),
        position.status === 'completed' ? 'pass' : position.status === 'canceled' ? 'fail' : 'info',
      ),
    ]
  })
  const reworked = sum((lot.follow_up_lots ?? []).filter((l) => l.disposition === 'rework').map((l) => l.quantity))
  const figures: KeyValue[] = [
    { label: t(`${R}.figures.ordered`), value: f.n(lot.quantity) },
    { label: t(`${R}.figures.completed`), value: f.n(lot.quantity_completed) },
    { label: t(`${R}.figures.scrapped`), value: f.n(lot.quantity_scrapped ?? 0) },
    { label: t(`${R}.figures.rework`), value: f.n(reworked) },
    { label: t(`${R}.figures.receiptRejected`), value: f.n(receiptRejected(data)) },
    {
      label: t(`${R}.figures.followUps`),
      value: (lot.follow_up_lots ?? []).map((l) => l.lot_number).join(', ') || REPORT_EMPTY,
    },
  ]
  return section(
    t(`${R}.sections.summary`),
    keyValueGrid(figures),
    subheading(t(`${R}.sections.inspections`)),
    rows.length > 0
      ? dataTable(
          [
            { header: t(`${R}.columns.position`), align: 'right' },
            { header: t(`${R}.columns.method`), width: '*' },
            { header: t(`${R}.columns.inspected`), align: 'right' },
            { header: t(`${R}.columns.accepted`), align: 'right' },
            { header: t(`${R}.columns.rejected`), align: 'right' },
            { header: t(`${R}.columns.status`) },
          ],
          rows,
        )
      : paragraph(t(`${R}.noInspections`), 'muted'),
  )
}

// ── Part and material ────────────────────────────────────────────────

function partSection(data: InspectionReportData, f: Format): Content {
  const { t } = f
  const lot = data.lot
  const item = data.madeItem
  const label = useMadeItemLabel()
  const drawings = data.madeItemFiles.filter((file) => file.category === 'drawing' || file.category === 'pdf')
  const items: KeyValue[] = [
    { label: t(`${R}.part.number`), value: label.format(lot.made_item_part_number, lot.made_item_revision) },
    { label: t(`${R}.part.article`), value: orDash(lot.made_item_article_name) },
    {
      label: t(`${R}.part.revision`),
      value: item?.revision_date
        ? t(`${R}.part.revisionValue`, { revision: orDash(item.revision), date: f.date(item.revision_date) })
        : orDash(item?.revision ?? lot.made_item_revision),
    },
    { label: t(`${R}.part.revisionNote`), value: orDash(item?.revision_note) },
    { label: t(`${R}.part.material`), value: orDash(lot.made_item_material) },
    { label: t(`${R}.part.mass`), value: item?.mass ? `${f.n(item.mass / 1000)} kg` : REPORT_EMPTY },
    { label: t(`${R}.part.baseSize`), value: orDash(item?.base_size) },
    { label: t(`${R}.part.drawing`), value: drawings.map((file) => file.file_name).join(', ') || REPORT_EMPTY },
  ]
  const grid = keyValueGrid(items, 1)
  return section(
    t(`${R}.sections.part`),
    data.partImage ? twoColumns(grid, group([picture(data.partImage, [240, 160])], 'none')) : grid,
  )
}

function materialSection(data: InspectionReportData, f: Format): Content {
  const { t } = f
  const lot = data.lot
  const approval = (() => {
    switch (lot.source_approval_status) {
      case 'approved':
        return t(`${R}.material.approvedOn`, { date: lot.source_approved_date ? f.dateTime(lot.source_approved_date) : REPORT_EMPTY })
      case 'rejected':
        return t(`${R}.material.rejected`, { reason: orDash(lot.source_rejection_reason) })
      case 'pending':
        return t(`${R}.material.pending`)
      case 'awaiting_first_step':
        return t(`${R}.material.awaitingFirstStep`)
      case 'supplier_sourced':
        return t(`${R}.material.supplierSourced`)
      default:
        return t(`${R}.material.notRequired`)
    }
  })()
  return section(
    t(`${R}.sections.material`),
    keyValueGrid(
      [
        { label: t(`${R}.material.source`), value: [lot.source_label, lot.source_sublabel].filter(Boolean).join(', ') || REPORT_EMPTY },
        { label: t(`${R}.material.order`), value: orDash(lot.source_order_number) },
        { label: t(`${R}.material.delivered`), value: lot.source_delivery_date ? f.dateTime(lot.source_delivery_date) : REPORT_EMPTY },
        { label: t(`${R}.material.approval`), value: approval },
      ],
      1,
    ),
  )
}

// ── Inspections ──────────────────────────────────────────────────────

function dispositionText(c: ProductionOrderCompletionResponse, f: Format): string {
  if (c.quantity_rejected <= 0) return REPORT_EMPTY
  return f.t(`${R}.dispositionValue`, { rework: f.n(c.quantity_rework ?? 0), scrap: f.n(c.quantity_scrap ?? 0) })
}

function resultsTable(order: ProductionOrderResponse, f: Format): Content {
  const { t } = f
  const completions = completionsOf(order)
  if (completions.length === 0) return paragraph(t(`${R}.noResults`), 'muted')
  return dataTable(
    [
      { header: t(`${R}.columns.date`) },
      { header: t(`${R}.columns.inspector`), width: '*' },
      { header: t(`${R}.columns.accepted`), align: 'right' },
      { header: t(`${R}.columns.rejected`), align: 'right' },
      { header: t(`${R}.columns.reason`) },
      { header: t(`${R}.columns.disposition`) },
    ],
    completions.map((c) => [
      cell(f.date(c.completion_date), { noWrap: true }),
      c.note
        ? noteCell(orDash(c.operator?.full_name), [c.note])
        : orDash(c.operator?.full_name),
      f.n(c.quantity_accepted),
      c.quantity_rejected > 0 ? cell(f.n(c.quantity_rejected), { style: 'alert' }) : f.n(0),
      reason(c.reject_reason, t),
      dispositionText(c, f),
    ]),
    'small',
  )
}

function evidenceTable(data: InspectionReportData, order: ProductionOrderResponse, f: Format): Content {
  const { t } = f
  const files = data.filesByOrder.get(order.id) ?? []
  if (files.length === 0) return paragraph(t(`${R}.noEvidence`), 'muted')
  return dataTable(
    [
      { header: t(`${R}.columns.file`), width: '*' },
      { header: t(`${R}.columns.uploaded`) },
      { header: t(`${R}.columns.size`), align: 'right' },
      { header: t(`${R}.columns.fingerprint`) },
    ],
    files.map((file) => [
      file.file_name,
      cell(f.dateTime(file.created), { noWrap: true }),
      `${f.n(Math.max(1, Math.round(file.size_bytes / 1024)))} kB`,
      cell(file.sha256 ? file.sha256.slice(0, 16) : REPORT_EMPTY, { style: 'muted' }),
    ]),
    'small',
  )
}

function inspectionBlock(data: InspectionReportData, position: LotPositionResponse, f: Format): Content {
  const { t } = f
  const step = inspectionStepOf(position)!
  const method = step.inspection_method_id != null ? data.methods.get(step.inspection_method_id) : undefined
  const orders = ordersOf(data, position)
  const head: Content[] = [
    subheading(t(`${R}.positionTitle`, { position: position.sequence, method: methodOf(step) })),
    keyValueGrid(
      [
        { label: t(`${R}.inspection.method`), value: orDash(localizeLabel(method?.description)) },
        { label: t(`${R}.inspection.instruction`), value: orDash(step.note) },
        {
          label: t(`${R}.inspection.evidence`),
          value: t(step.inspection_method_requires_evidence ? `${R}.inspection.evidenceRequired` : `${R}.inspection.evidenceOptional`),
        },
      ],
      1,
    ),
  ]
  const perOrder = orders.map((order) =>
    group(
      [
        keyValueGrid(
          [
            { label: t(`${R}.inspection.order`), value: order.production_order_number },
            { label: t(`${R}.inspection.equipment`), value: order.machine_internal_name || t(`${R}.inspection.manual`) },
            { label: t(`${R}.inspection.started`), value: byAt(order.started_operator?.full_name, order.actual_start, f) },
            { label: t(`${R}.inspection.finished`), value: order.actual_end ? f.dateTime(order.actual_end) : REPORT_EMPTY },
          ],
          2,
          'before',
        ),
        paragraph(t(`${R}.inspection.results`), 'label', 'before'),
        resultsTable(order, f),
        paragraph(t(`${R}.inspection.evidenceFiles`), 'label', 'before'),
        evidenceTable(data, order, f),
      ],
      'after',
    ),
  )
  return group([keepTogether(head), ...(perOrder.length > 0 ? perOrder : [paragraph(t(`${R}.noOrders`), 'muted')])], 'after')
}

function inspectionsSection(data: InspectionReportData, f: Format): Content {
  const positions = inspectionPositions(data.lot)
  if (positions.length === 0) return section(f.t(`${R}.sections.inspectionDetails`), paragraph(f.t(`${R}.noInspections`), 'muted'))
  return section(f.t(`${R}.sections.inspectionDetails`), ...positions.map((position) => inspectionBlock(data, position, f)))
}

// ── Production and goods receipt ─────────────────────────────────────

function productionSection(data: InspectionReportData, f: Format): Content {
  const { t } = f
  const rows: TableCell[][] = [...(data.lot.positions ?? [])]
    .filter((position) => inspectionStepOf(position) === null)
    .sort(bySequence)
    .map((position) => {
      const orders = ordersOf(data, position)
      const completions = orders.flatMap(completionsOf)
      const where = position.supplier_name
        ? t(`${R}.production.external`, { supplier: position.supplier_name, order: orDash(position.order_number) })
        : orders.map((o) => [o.production_order_number, o.machine_internal_name].filter(Boolean).join(', ')).join('; ') || REPORT_EMPTY
      const scrapped = sum(completions.map((c) => c.quantity_scrap ?? 0))
      return [
        cell(String(position.sequence), { align: 'right' }),
        (position.steps ?? []).map(methodOf).join(', '),
        where,
        f.n(position.quantity_completed),
        scrapped > 0 ? cell(f.n(scrapped), { style: 'alert' }) : f.n(0),
      ]
    })
  if (rows.length === 0) return section(t(`${R}.sections.production`), paragraph(t(`${R}.noProduction`), 'muted'))
  return section(
    t(`${R}.sections.production`),
    dataTable(
      [
        { header: t(`${R}.columns.position`), align: 'right' },
        { header: t(`${R}.columns.steps`), width: '*' },
        { header: t(`${R}.columns.where`), width: '*' },
        { header: t(`${R}.columns.completed`), align: 'right' },
        { header: t(`${R}.columns.scrapped`), align: 'right' },
      ],
      rows,
      'small',
    ),
  )
}

function receiptSection(data: InspectionReportData, f: Format): Content[] {
  const { t } = f
  const blocks: Content[] = []
  for (const position of sortedBySequence(data.lot.positions)) {
    if (position.order_id == null) continue
    const order = data.ordersById.get(position.order_id)
    const item = order?.items.find((line) => line.lot_position_id === position.id)
    if (!order || !item) continue
    const provisions = data.provisionsByPosition.get(position.id) ?? []
    const records = item.delivery_records ?? []
    blocks.push(
      keepTogether(
        [
          subheading(
            t(`${R}.receipt.title`, {
              position: position.sequence,
              supplier: orDash(item.supplier_name ?? position.supplier_name),
            }),
          ),
          keyValueGrid(
            [
              { label: t(`${R}.receipt.order`), value: t(`${R}.receipt.orderValue`, { order: order.order_number, line: item.position }) },
              { label: t(`${R}.receipt.ordered`), value: item.ordered_date ? f.date(item.ordered_date) : REPORT_EMPTY },
              {
                label: t(`${R}.receipt.provided`),
                value:
                  provisions.map((p) => t(`${R}.receipt.provisionValue`, { quantity: f.n(p.quantity), date: f.date(p.provision_date) })).join('; ') ||
                  REPORT_EMPTY,
              },
              { label: t(`${R}.receipt.delivered`), value: f.n(item.quantity_delivered ?? 0) },
            ],
            2,
          ),
          records.length > 0
            ? dataTable(
                [
                  { header: t(`${R}.columns.date`) },
                  { header: t(`${R}.columns.received`), align: 'right' },
                  { header: t(`${R}.columns.rejected`), align: 'right' },
                  { header: t(`${R}.columns.reason`), width: '*' },
                  { header: t(`${R}.columns.receiver`) },
                ],
                records.map((record) => [
                  cell(f.dateTime(record.delivery_date), { noWrap: true }),
                  f.n(record.quantity),
                  record.quantity_rejected ? cell(f.n(record.quantity_rejected), { style: 'alert' }) : f.n(0),
                  record.quantity_rejected
                    ? noteCell(
                        [reason(record.rejection_reason, t), record.rejection_outcome ? `, ${t(`orders.delivery.reject.outcomeOptions.${record.rejection_outcome}`)}` : ''].join(''),
                        record.rejection_note ? [record.rejection_note] : [],
                      )
                    : REPORT_EMPTY,
                  orDash(record.receiver?.full_name),
                ]),
                'small',
              )
            : paragraph(t(`${R}.noDeliveries`), 'muted'),
        ],
        'after',
      ),
    )
  }
  return blocks.length > 0 ? [section(t(`${R}.sections.receipt`), ...blocks)] : []
}

// ── Nonconformities and history ──────────────────────────────────────

function nonconformitiesSection(data: InspectionReportData, f: Format): Content {
  const { t } = f
  const rows: Array<{ at: string; row: TableCell[] }> = []
  for (const position of data.lot.positions ?? []) {
    const isInspection = inspectionStepOf(position) !== null
    for (const order of ordersOf(data, position)) {
      for (const c of completionsOf(order)) {
        const pieces = isInspection ? c.quantity_rejected : (c.quantity_scrap ?? 0)
        if (pieces <= 0) continue
        rows.push({
          at: c.created,
          row: [
            cell(f.date(c.completion_date), { noWrap: true }),
            t(`${R}.nonconformity.at`, { position: position.sequence, order: order.production_order_number }),
            f.n(pieces),
            reason(isInspection ? c.reject_reason : c.scrap_reason, t),
            isInspection ? dispositionText(c, f) : t(`${R}.nonconformity.scrapped`),
          ],
        })
      }
    }
    const order = position.order_id != null ? data.ordersById.get(position.order_id) : undefined
    const item = order?.items.find((line) => line.lot_position_id === position.id)
    for (const record of item?.delivery_records ?? []) {
      if (!record.quantity_rejected) continue
      rows.push({
        at: record.delivery_date,
        row: [
          cell(f.date(record.delivery_date.slice(0, 10)), { noWrap: true }),
          t(`${R}.nonconformity.receipt`, { position: position.sequence, supplier: orDash(item?.supplier_name) }),
          f.n(record.quantity_rejected),
          reason(record.rejection_reason, t),
          record.rejection_outcome ? t(`orders.delivery.reject.outcomeOptions.${record.rejection_outcome}`) : REPORT_EMPTY,
        ],
      })
    }
  }
  rows.sort((a, b) => a.at.localeCompare(b.at))
  const followUps = data.lot.follow_up_lots ?? []
  return section(
    t(`${R}.sections.nonconformities`),
    rows.length > 0
      ? dataTable(
          [
            { header: t(`${R}.columns.date`) },
            { header: t(`${R}.columns.where`), width: '*' },
            { header: t(`${R}.columns.pieces`), align: 'right' },
            { header: t(`${R}.columns.reason`) },
            { header: t(`${R}.columns.outcome`) },
          ],
          rows.map((entry) => entry.row),
          'small',
        )
      : paragraph(t(`${R}.noNonconformities`), 'muted'),
    keepTogether([
      subheading(t(`${R}.followUpLots`)),
      followUps.length > 0
        ? dataTable(
            [
              { header: t(`${R}.columns.lot`) },
              { header: t(`${R}.columns.disposition`), width: '*' },
              { header: t(`${R}.columns.pieces`), align: 'right' },
            ],
            followUps.map((l) => [l.lot_number, t(`${R}.dispositions.${l.disposition}`), f.n(l.quantity)]),
            'small',
          )
        : paragraph(t(`${R}.noFollowUps`), 'muted'),
    ]),
  )
}

// The events a reader of an inspection report needs; planning and step
// edits stay in the app's history.
const QUALITY_EVENTS = new Set([
  'lot_created',
  'lot_source_approved',
  'lot_source_rejected',
  'lot_material_source_switched',
  'lot_held',
  'lot_resumed',
  'lot_closed_short',
  'lot_completed',
  'lot_canceled',
  'lot_scrapped',
  'inspection_recorded',
  'pieces_scrapped',
  'pieces_lost_at_receipt',
  'wip_dropped',
  'raw_material_left_over',
  'rework_lot_created',
  'replacement_lot_created',
  'replacement_skipped',
])

function historySection(data: InspectionReportData, f: Format): Content {
  const { t } = f
  const events = data.events
    .filter((event) => QUALITY_EVENTS.has(event.event_type))
    .sort((a, b) => a.occurred_at.localeCompare(b.occurred_at))
  return section(
    t(`${R}.sections.history`),
    events.length > 0
      ? dataTable(
          [
            { header: t(`${R}.columns.when`) },
            { header: t(`${R}.columns.by`) },
            { header: t(`${R}.columns.event`), width: '*' },
          ],
          events.map((event) => [
            cell(f.dateTime(event.occurred_at), { noWrap: true }),
            orDash(event.actor_full_name),
            t(lotEventLabelKey(event.event_type)),
          ]),
          'small',
        )
      : paragraph(t(`${R}.noHistory`), 'muted'),
    footnote(t(`${R}.historyNote`)),
  )
}

// ── Report ───────────────────────────────────────────────────────────

/** Builds the report from loaded data; exported so it can be tested without the API. */
export function buildInspectionReport(data: InspectionReportData, context: ReportContext) {
  const { formatNumber } = useLocaleFormat(context.locale)
  const f: Format = {
    t: context.t,
    n: (value) => formatNumber(value, { maximumFractionDigits: 3 }),
    dateTime: context.dateTime,
    date: context.date,
  }
  const lot = data.lot
  const label = useMadeItemLabel()
  return {
    kind: context.t(`${R}.kind`),
    title: lot.lot_number,
    subtitle: [lot.made_item_article_name, label.format(lot.made_item_part_number, lot.made_item_revision)]
      .filter(Boolean)
      .join(', '),
    details: details(lot, f),
    notice: statusNotice(lot, f),
    identity: { publicId: lot.public_id, reference: context.t(`${R}.identity`, { lot: lot.lot_number }) },
    body: [
      summarySection(data, f),
      partSection(data, f),
      materialSection(data, f),
      inspectionsSection(data, f),
      productionSection(data, f),
      ...receiptSection(data, f),
      nonconformitiesSection(data, f),
      historySection(data, f),
    ],
  }
}

/** The inspection report of a lot; `title` names it in the export dialog, in the app's language. */
export function inspectionReportSpec(lot: Pick<LotResponse, 'id' | 'public_id'>, title: string): ReportSpec {
  return {
    title,
    printTarget: { document: 'inspection_report', rootPublicId: lot.public_id },
    build: async (context) => buildInspectionReport(await loadInspectionReportData(lot.id), context),
  }
}
