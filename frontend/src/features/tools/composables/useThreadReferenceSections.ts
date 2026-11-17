import { computed } from 'vue'
import type { ComputedRef, Ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import type { ToolReferenceRow } from '../components/ToolReferenceTable.vue'
import {
  CAP_SCREW_COUNTERBORES,
  CLEARANCE_HOLES,
  COUNTERSINKS_ISO_10642,
  COUNTERSINKS_ISO_15065,
  HEX_COUNTERBORES,
} from '../utils/threads/holes'
import { COARSE_THREADS, FINE_THREADS, findThread, threadGeometry, WIDTH_ACROSS_FLATS } from '../utils/threads/metric'
import type { MetricThread } from '../utils/threads/metric'
import { PROPERTY_CLASSES, TIGHTENING } from '../utils/threads/tightening'
import { LIMITS_6H_6G } from '../utils/threads/tolerances'

/** Number formatting of the threads tab, in the UI language. */
export function useThreadFormat() {
  const { formatNumber } = useLocaleFormat()

  function num(value: number, digits = 3): string {
    return formatNumber(value, { maximumFractionDigits: digits })
  }

  // Thread diameters and depths are given to three decimals, as in DIN 13.
  function fixed3(value: number): string {
    return formatNumber(value, { minimumFractionDigits: 3, maximumFractionDigits: 3 })
  }

  function mm(value: number): string {
    return `${num(value)} mm`
  }

  // Stress areas carry three significant digits, or four from 1000 mm² up.
  function area(value: number): string {
    const digits = value < 10 ? 2 : value < 100 ? 1 : 0
    return formatNumber(value, { minimumFractionDigits: digits, maximumFractionDigits: digits })
  }

  function threadLabel(th: { d: number; pitch: number; fine: boolean }): string {
    return th.fine ? `M${num(th.d)} × ${num(th.pitch)}` : `M${num(th.d)}`
  }

  return { num, fixed3, mm, area, threadLabel }
}

/** The drawing that explains a table's column symbols. */
export type ThreadSketch = 'profile' | 'clearance' | 'counterbore' | 'countersink' | 'tightening'

export interface ThreadReferenceTable {
  key: string
  sketch: ThreadSketch
  title: string
  unit: string
  rowHeader: string
  columns: string[]
  rows: ToolReferenceRow[]
  activeRow: string | null
  activeColumn: number | null
  note?: string
}

export const sizeKey = (d: number) => `M${d}`

/**
 * The reference tables of the threads tab, grouped in sections, with the row of
 * the selected thread or size and the column of the selected property class
 * marked.
 */
export function useThreadReferenceSections(options: {
  threadCode: Ref<string>
  thread: ComputedRef<MetricThread>
  classIndex: ComputedRef<number>
  hasTightening: ComputedRef<boolean>
}) {
  const { t } = useI18n()
  const { num, fixed3, area, threadLabel } = useThreadFormat()
  const { threadCode, thread, classIndex } = options
  const activeSize = computed(() => sizeKey(thread.value.d))

  const col = (key: string, params?: Record<string, unknown>) =>
    params ? t(`tools.threads.tables.columns.${key}`, params) : t(`tools.threads.tables.columns.${key}`)
  const dash = (value: number | null | undefined, format: (v: number) => string = num) =>
    value === null || value === undefined ? '–' : format(value)

  const threadTables = computed<ThreadReferenceTable[]>(() => [
    {
      key: 'coarse',
      sketch: 'profile',
      title: t('tools.threads.tables.coarse'),
      unit: t('tools.threads.tables.unitMm'),
      rowHeader: t('tools.threads.tables.rowThread'),
      columns: ['pitch', 'd2', 'd3', 'D1', 'h3', 'H1', 'stressArea', 'tapDrill', 'widthAcrossFlats'].map((k) => col(k)),
      rows: COARSE_THREADS.map((th) => {
        const g = threadGeometry(th.d, th.pitch)
        return {
          key: th.code,
          label: threadLabel(th),
          cells: [
            num(th.pitch), fixed3(g.d2), fixed3(g.d3), fixed3(g.D1), fixed3(g.h3), fixed3(g.H1),
            area(g.stressArea), num(g.tapDrill), dash(WIDTH_ACROSS_FLATS[th.d]),
          ],
        }
      }),
      activeRow: threadCode.value,
      activeColumn: null,
    },
    {
      key: 'fine',
      sketch: 'profile',
      title: t('tools.threads.tables.fine'),
      unit: t('tools.threads.tables.unitMm'),
      rowHeader: t('tools.threads.tables.rowThread'),
      columns: ['pitch', 'd2', 'd3', 'D1', 'stressArea', 'tapDrill'].map((k) => col(k)),
      rows: FINE_THREADS.map((th) => {
        const g = threadGeometry(th.d, th.pitch, true)
        return {
          key: th.code,
          label: threadLabel(th),
          cells: [num(th.pitch), fixed3(g.d2), fixed3(g.d3), fixed3(g.D1), area(g.stressArea), num(g.tapDrill)],
        }
      }),
      activeRow: threadCode.value,
      activeColumn: null,
    },
    {
      key: 'limits',
      sketch: 'profile',
      title: t('tools.threads.tables.limits'),
      unit: t('tools.threads.tables.unitMm'),
      rowHeader: t('tools.threads.tables.rowThread'),
      columns: ['Dmin', 'D2min', 'D2max', 'D1min', 'D1max', 'dmax', 'dmin', 'd2max', 'd2min', 'd3max', 'd3min'].map((k) =>
        col(k),
      ),
      rows: Object.entries(LIMITS_6H_6G).map(([code, l]) => ({
        key: code,
        label: threadLabel(findThread(code) as MetricThread),
        cells: [
          l.internal.Dmin, ...l.internal.D2, ...l.internal.D1, ...l.external.d, ...l.external.d2, ...l.external.d3,
        ].map(fixed3),
      })),
      activeRow: threadCode.value,
      activeColumn: null,
    },
  ])

  const holeTables = computed<ThreadReferenceTable[]>(() => [
    {
      key: 'clearance',
      sketch: 'clearance',
      title: t('tools.threads.tables.clearance'),
      unit: t('tools.threads.tables.unitMm'),
      rowHeader: t('tools.threads.tables.rowThread'),
      columns: ['fine', 'medium', 'coarse'].map((k) => col(k)),
      rows: Object.entries(CLEARANCE_HOLES)
        .sort(([a], [b]) => Number(a) - Number(b))
        .map(([d, values]) => ({ key: sizeKey(Number(d)), label: `M${num(Number(d))}`, cells: values.map((v) => num(v)) })),
      activeRow: activeSize.value,
      activeColumn: null,
    },
    {
      key: 'capScrew',
      sketch: 'counterbore',
      title: t('tools.threads.tables.capScrew'),
      unit: t('tools.threads.tables.unitMm'),
      rowHeader: t('tools.threads.tables.rowThread'),
      columns: [
        col('dh'),
        ...[1, 2, 3, 4, 5, 6].map((n) => col('series', { n })),
        col('depthIso1207'),
        col('depthIso4762'),
        col('depthDin7984'),
      ],
      rows: Object.entries(CAP_SCREW_COUNTERBORES)
        .sort(([a], [b]) => Number(a) - Number(b))
        .map(([d, row]) => ({
          key: sizeKey(Number(d)),
          label: `M${num(Number(d))}`,
          cells: [
            num(row.dh),
            ...row.series.map((v) => dash(v)),
            dash(row.depth.iso1207),
            dash(row.depth.iso4762),
            dash(row.depth.din7984),
          ],
        })),
      activeRow: activeSize.value,
      activeColumn: null,
      note: t('tools.threads.tables.capScrewSeries'),
    },
    {
      key: 'hex',
      sketch: 'counterbore',
      title: t('tools.threads.tables.hex'),
      unit: t('tools.threads.tables.unitMm'),
      rowHeader: t('tools.threads.tables.rowThread'),
      columns: [col('widthAcrossFlats'), col('dh'), ...[1, 2, 3].map((n) => col('series', { n })), col('depth')],
      rows: Object.entries(HEX_COUNTERBORES)
        .sort(([a], [b]) => Number(a) - Number(b))
        .map(([d, row]) => ({
          key: sizeKey(Number(d)),
          label: `M${num(Number(d))}`,
          cells: [num(row.widthAcrossFlats), num(row.dh), ...row.series.map((v) => num(v)), num(row.depth)],
        })),
      activeRow: activeSize.value,
      activeColumn: null,
      note: t('tools.threads.tables.hexSeries'),
    },
    {
      key: 'countersinkSlotted',
      sketch: 'countersink',
      title: t('tools.threads.tables.countersinkSlotted'),
      unit: t('tools.threads.tables.unitMm'),
      rowHeader: t('tools.threads.tables.rowThread'),
      columns: ['d1', 'd2Min', 'd2Max', 't1'].map((k) => col(k)),
      rows: Object.entries(COUNTERSINKS_ISO_15065)
        .sort(([a], [b]) => Number(a) - Number(b))
        .map(([d, row]) => ({
          key: sizeKey(Number(d)),
          label: `M${num(Number(d))}`,
          cells: [row.d1, row.d2Min, row.d2Max, row.depth].map((v) => num(v)),
        })),
      activeRow: activeSize.value,
      activeColumn: null,
    },
    {
      key: 'countersinkSocket',
      sketch: 'countersink',
      title: t('tools.threads.tables.countersinkSocket'),
      unit: t('tools.threads.tables.unitMm'),
      rowHeader: t('tools.threads.tables.rowThread'),
      columns: ['d1', 'd2', 't1'].map((k) => col(k)),
      rows: Object.entries(COUNTERSINKS_ISO_10642)
        .sort(([a], [b]) => Number(a) - Number(b))
        .map(([d, row]) => ({
          key: sizeKey(Number(d)),
          label: `M${num(Number(d))}`,
          cells: [row.d1, row.d2, row.depth].map((v) => num(v)),
        })),
      activeRow: activeSize.value,
      activeColumn: null,
    },
  ])

  const tighteningTables = computed<ThreadReferenceTable[]>(() => {
    const activeRow = options.hasTightening.value ? activeSize.value : null
    const base = (key: 'torque' | 'preload', unitKey: string): ThreadReferenceTable => ({
      key,
      sketch: 'tightening',
      title: t(`tools.threads.tables.${key}`),
      unit: t(`tools.threads.tables.${unitKey}`),
      rowHeader: t('tools.threads.tables.rowThread'),
      columns: [col('pitch'), col('stressArea'), ...PROPERTY_CLASSES],
      rows: TIGHTENING.map((row) => ({
        key: sizeKey(row.d),
        label: `M${num(row.d)}`,
        cells: [num(row.pitch), num(row.stressArea), ...row[key].map((v) => num(v, 2))],
      })),
      activeRow,
      activeColumn: 2 + classIndex.value,
    })
    return [base('torque', 'unitTorque'), base('preload', 'unitPreload')]
  })

  const sections = computed(() => [
    { key: 'threads', title: t('tools.threads.tables.sectionThreads'), tables: threadTables.value },
    { key: 'holes', title: t('tools.threads.tables.sectionHoles'), tables: holeTables.value },
    { key: 'tightening', title: t('tools.threads.tables.sectionTightening'), tables: tighteningTables.value },
  ])

  return sections
}
