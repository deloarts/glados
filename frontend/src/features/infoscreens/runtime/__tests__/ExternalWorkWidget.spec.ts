import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'

import ExternalWorkWidget from '../components/widgets/ExternalWorkWidget.vue'
import type { WidgetConfigOf, WidgetDataOf } from '../types/infoscreenFeed'
import type { ExternalWorkRow } from '../utils/externalWorkGroups'

// Tuesday the 10th.
const NOW = new Date('2026-11-10T10:00:00Z')

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] })
  vi.setSystemTime(NOW)
})

afterEach(() => {
  vi.useRealTimers()
})

function row(overrides: Partial<ExternalWorkRow> = {}): ExternalWorkRow {
  return {
    lot_number: 'LOT-26-00001',
    part_number: 'I-26-00102',
    item_name: 'Messerhalter',
    quantity: 10,
    methods: ['Brünieren'],
    supplier_name: 'Härterei Demo',
    supplier_suggested: true,
    latest_pickup_date: '2026-11-10',
    ready_from: null,
    ready_now: true,
    due_back_date: '2026-11-14',
    alert: null,
    days_late: null,
    thumbnail_url: null,
    ...overrides,
  }
}

function config(layout: 'days' | 'suppliers'): WidgetConfigOf<'external_work'> {
  return {
    type: 'external_work',
    title: null,
    horizon_days: 7,
    show_overdue: true,
    fabrication_method_ids: [],
    only_with_supplier: false,
    layout,
  }
}

const ROWS: ExternalWorkRow[] = [
  row({ latest_pickup_date: '2026-11-07', alert: 'overdue', days_late: 3 }),
  row({ item_name: 'Führungsleiste' }),
  row({
    item_name: 'Konsole',
    methods: ['Blechbearbeitung', 'Beschichten'],
    supplier_name: 'Oberflächen Demo',
    supplier_suggested: false,
    latest_pickup_date: '2026-11-11',
    ready_now: false,
    ready_from: '2026-11-12',
    alert: 'not_ready_in_time',
  }),
  row({ item_name: 'Welle', latest_pickup_date: '2026-11-13', ready_now: false, ready_from: '2026-11-12' }),
]

function mount(layout: 'days' | 'suppliers', rows = ROWS) {
  return mountWithApp(ExternalWorkWidget, {
    props: {
      config: config(layout),
      data: { type: 'external_work', rows } as WidgetDataOf<'external_work'>,
    },
  })
}

describe('external work widget', () => {
  it('sums up what goes out today, this week and what is critical', () => {
    const w = mount('days')

    const summary = w.get('[data-testid="external-work-summary"]').text()
    expect(summary).toContain('Out today 2')
    expect(summary).toContain('This week 4')
    expect(summary).toContain('2 critical')
  })

  it('groups the parts by the day they must leave, today standing out', () => {
    const w = mount('days')

    const days = w.findAll('[data-testid="external-work-day"]')
    expect(days.map((d) => d.get('h3').text())).toEqual([
      'Overdue 1',
      'Today 1',
      'Tomorrow 1',
      expect.stringContaining('Friday'),
    ])
    expect(days[1]!.classes()).toContain('external-work-day--today')
    expect(days[0]!.text()).toContain('3 days late')
    expect(days[1]!.text()).toContain('Brünieren → Härterei Demo')
    expect(days[2]!.text()).toContain('Not ready in time')
    expect(days[3]!.text()).toContain('Ready Thursday')
  })

  it('gives each supplier a lane with its next send-out day and how much is ready', () => {
    const w = mount('suppliers')

    const lanes = w.findAll('[data-testid="external-work-lane"]')
    expect(lanes).toHaveLength(2)
    expect(lanes[0]!.text()).toContain('Härterei Demo')
    expect(lanes[0]!.text()).toContain('2 of 3 ready')
    expect(lanes[1]!.text()).toContain('Oberflächen Demo')
    expect(lanes[1]!.text()).toContain('0 of 1 ready')
  })

  it('says so when nothing has to leave', () => {
    const w = mount('days', [])

    expect(w.text()).toContain('Nothing has to leave for a supplier')
  })
})
