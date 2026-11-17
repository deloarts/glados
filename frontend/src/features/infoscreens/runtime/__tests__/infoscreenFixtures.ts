import type { TerminalDeviceState } from '@/core/terminal/terminalApi'

import type {
  InfoscreenFeedPage,
  InfoscreenFeedResponse,
  InfoscreenLotRow,
  InfoscreenOrderCard,
  InfoscreenWidgetData,
} from '../types/infoscreenFeed'

export function deviceStateFixture(overrides: Partial<TerminalDeviceState> = {}): TerminalDeviceState {
  return {
    terminal_id: 7,
    status: 'approved',
    mode: 'infoscreen',
    name: 'Hall 2 Display',
    pairing_code: null,
    pairing_expires_at: null,
    infoscreen_id: 3,
    reload_requested_at: null,
    identify_requested_at: null,
    location: null,
    display_power: 'on',
    display_power_changes_at: null,
    broadcast: null,
    ...overrides,
  } as TerminalDeviceState
}

export function orderCardFixture(overrides: Partial<InfoscreenOrderCard> = {}): InfoscreenOrderCard {
  return {
    production_order_id: 11,
    lot_number: 'L-2026-0042',
    part_number: 'P-100',
    item_name: 'Bracket',
    project_number: 'PRJ-9',
    quantity: 12,
    status: 'in_progress',
    thumbnail_url: '/api/v1/web/terminal-device/thumbnails/card-token',
    ...overrides,
  } as InfoscreenOrderCard
}

export function lotRowFixture(overrides: Partial<InfoscreenLotRow> = {}): InfoscreenLotRow {
  return {
    lot_id: 21,
    lot_number: 'L-2026-0050',
    part_number: 'P-200',
    item_name: 'Housing',
    project_number: 'PRJ-1',
    customer_name: 'Acme Machines',
    target_date: '2026-11-02',
    status: 'planned',
    days_late: null,
    thumbnail_url: '/api/v1/web/terminal-device/thumbnails/lot-token',
    ...overrides,
  } as InfoscreenLotRow
}

export function pageFixture(
  layout: InfoscreenFeedPage['layout'],
  slots: InfoscreenFeedPage['slots'],
): InfoscreenFeedPage {
  return { layout, slots } as InfoscreenFeedPage
}

/**
 * A two-page screen: every widget type on a 2x2 grid and a main/side page,
 * with matching data in `widgets[p][s]`.
 */
export function feedFixture(overrides: Partial<InfoscreenFeedResponse> = {}): InfoscreenFeedResponse {
  const pages = [
    pageFixture('grid_2x2', [
      { type: 'machine_board', title: null, machine_ids: [1], pool_ids: [], next_count: 3 },
      { type: 'lots_due', title: null, horizon_days: 7, pool_ids: [], show_customer: false },
      { type: 'late_lots', title: 'Late in Hall 2', show_customer: true },
      { type: 'qa_queue', title: null },
    ] as InfoscreenFeedPage['slots']),
    pageFixture('main_side', [
      { type: 'deliveries_expected', title: null, horizon_days: 0 },
      { type: 'clock', title: null, show_date: true, show_next_holiday: true },
    ] as InfoscreenFeedPage['slots']),
  ]
  const widgets = [
    [
      {
        type: 'machine_board',
        machines: [
          {
            machine_id: 1,
            machine_name: 'DMG Mori 1',
            state: 'running',
            downtime_reason: null,
            current: orderCardFixture(),
            next: [orderCardFixture({ production_order_id: 12, lot_number: 'L-2026-0043' })],
          },
          {
            machine_id: 2,
            machine_name: 'Trumpf Laser',
            state: 'down',
            downtime_reason: 'Spindle repair',
            current: null,
            next: [],
          },
        ],
        pools: [
          {
            pool_id: 4,
            pool_name: 'Lasers',
            waiting: [
              orderCardFixture({ production_order_id: 31, lot_number: 'L-2026-0060' }),
              orderCardFixture({ production_order_id: 32, lot_number: 'L-2026-0061', thumbnail_url: null }),
            ],
            waiting_total: 5,
          },
          { pool_id: 5, pool_name: 'Saws', waiting: [], waiting_total: 0 },
        ],
      },
      {
        type: 'lots_due',
        lots: [
          lotRowFixture({ lot_id: 20, lot_number: 'L-2026-0049', target_date: '2026-10-28', days_late: 2 }),
          lotRowFixture(),
        ],
      },
      { type: 'late_lots', lots: [lotRowFixture({ lot_id: 22, lot_number: 'L-2026-0031', days_late: 3 })] },
      {
        type: 'qa_queue',
        tasks: [
          {
            task_id: 5,
            lot_number: 'L-2026-0040',
            part_number: 'P-300',
            item_name: 'Shaft',
            status: 'queued',
            since: '2026-10-29T13:00:00Z',
            thumbnail_url: null,
          },
        ],
      },
    ],
    [
      {
        type: 'deliveries_expected',
        deliveries: [
          {
            order_number: 'PO-77',
            part_number: 'B-10',
            item_name: 'Bearing 6204',
            quantity: 40,
            unit: 'pcs',
            supplier_name: 'Bearings Ltd',
            expected_date: '2026-10-30',
            thumbnail_url: '/api/v1/web/terminal-device/thumbnails/delivery-token',
          },
        ],
      },
      { type: 'clock', next_holiday: { date: '2026-11-01', name: 'All Saints' } },
    ],
  ] as InfoscreenWidgetData[][]

  return {
    infoscreen: {
      id: 3,
      name: 'Hall 2',
      color_mode: 'dark',
      theme_preset: 'Nora',
      primary_color: 'emerald',
      rotation_seconds: 30,
      show_header: true,
      header: { left: ['logo', 'title'], center: [], right: ['clock'], text: null },
      show_footer: false,
      footer: { left: [], center: [], right: ['last_updated'], text: null },
      pages,
    },
    widgets,
    banner: null,
    broadcast: null,
    language: 'enGB',
    next_holiday: null,
    generated_at: '2026-10-30T08:00:00Z',
    backend_version: '1.4.0',
    timezone: 'Europe/Vienna',
    ...overrides,
  } as InfoscreenFeedResponse
}
