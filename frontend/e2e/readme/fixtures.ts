/**
 * A small, made-up shop for the README pictures: five machines, a handful of
 * lots across three projects and the production orders that plan them. Every
 * name is generic, so the pictures never show real customer or company data.
 * The shapes are typed against the generated web schema, so a changed
 * response fails `npm run type-check` here instead of rendering a blank panel.
 */
import type { components } from '../../src/core/api/generated/webSchema'
import { NOW, madeItems } from '../visual/fixtures'

type Schemas = components['schemas']

const TODAY = NOW.slice(0, 10)

function uuid(n: number): string {
  return `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`
}

/** The date `offset` days after the fixed "today", as YYYY-MM-DD. */
function day(offset: number): string {
  const date = new Date(`${TODAY}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + offset)
  return date.toISOString().slice(0, 10)
}

/** A timestamp on a shop day, `hour` in UTC. */
function at(offset: number, hour: number): string {
  const whole = Math.floor(hour)
  const minutes = Math.round((hour - whole) * 60)
  return `${day(offset)}T${String(whole).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:00Z`
}

const PEOPLE: [string, string][] = [
  ['avery', 'Avery Example'],
  ['jordan', 'Jordan Smith'],
  ['sam', 'Sam Taylor'],
  ['robin', 'Robin Lee'],
  ['casey', 'Casey Morgan'],
]

export const people: Schemas['PublicUserResponse'][] = PEOPLE.map(([username, full_name], index) => ({
  id: index + 1,
  public_id: uuid(index + 1),
  username,
  full_name,
  has_avatar: false,
}))

export const userDirectory: Schemas['UserSummaryResponse'][] = people.map((person) => ({
  ...person,
  is_active: true,
  is_service_account: false,
  is_shared_account: false,
  is_systemuser: false,
}))

const avery = people[0]!

const METHODS: [string, string][] = [
  ['Sawing', '#64748b'],
  ['Milling', '#2563eb'],
  ['Turning', '#16a34a'],
  ['Laser cutting', '#dc2626'],
  ['Deburring', '#d97706'],
]

const fabricationMethods: Schemas['FabricationMethodResult'][] = METHODS.map(([name, color], index) => ({
  id: index + 1,
  public_id: uuid(2000 + index),
  name: { enGB: name },
  description: { enGB: '' },
  label_color: color,
  label_font_color: '#ffffff',
  lead_time_days: null,
  wait_after_minutes: null,
  default_supplier_id: null,
  default_for_assemblies: false,
  required_external: false,
  requires_machine: true,
  archived: false,
  sort_order: index,
  created: NOW,
  changed: NOW,
  creator_id: 1,
  creator: avery,
  changed_by_id: null,
  changed_by: null,
}))

type MachineStatus = Schemas['ProductionMachineStatus']

const MACHINES: [string, string, number, MachineStatus][] = [
  ['MILL-01', 'Vertical mill 650', 2, 'running'],
  ['MILL-02', 'Five-axis mill 500', 2, 'running'],
  ['LATHE-01', 'CNC lathe 300', 3, 'idle'],
  ['LASER-01', 'Fibre laser 3015', 4, 'running'],
  ['SAW-01', 'Band saw 260', 1, 'paused'],
]

/** Filled in once the orders exist, so a machine lists what runs on it. */
const activeOrders = new Map<number, Schemas['ActiveProductionOrderResponse'][]>()

export function machines(): Schemas['ProductionMachineResponse'][] {
  return MACHINES.map(([internal_name, model, method, status], index) => ({
    id: index + 1,
    public_id: uuid(3000 + index),
    internal_name,
    vendor: 'Generic',
    model,
    status,
    is_qa_machine: false,
    max_part_dimension: null,
    note: null,
    open_downtime: null,
    fabrication_method_ids: [method],
    fabrication_methods: [fabricationMethods[method - 1]!],
    active_orders: activeOrders.get(index + 1) ?? [],
    live_order_count: activeOrders.get(index + 1)?.length ?? 0,
    archived: false,
    changes: [],
    created: NOW,
    changed: null,
    creator_id: 1,
    creator_full_name: avery.full_name,
    changed_by_id: null,
    changed_by_full_name: null,
  }))
}

export function machinePools(): Schemas['MachinePoolResponse'][] {
  const all = machines()
  return [
    {
      id: 1,
      public_id: uuid(3100),
      name: 'Milling',
      note: null,
      machine_ids: [1, 2],
      machines: [all[0]!, all[1]!],
      archived: false,
      changes: [],
      created: NOW,
      changed: null,
      creator_id: 1,
      creator_full_name: avery.full_name,
      changed_by_id: null,
      changed_by_full_name: null,
    },
  ]
}

const PROJECTS: [number, string, string][] = [
  [1, '26-014', 'Acme Automation'],
  [2, '26-017', 'Example Conveyors'],
  [3, '26-021', 'Sample Packaging'],
]

type Urgency = Schemas['UrgencyClass']
type LotStatus = Schemas['LotStatus']

/**
 * One lot: the made item it produces, the project it is for, how many, its
 * status, priority, target day and the steps it runs through. A step names a
 * machine, its first shop day, start hour, length in hours and how far it is.
 */
interface LotSpec {
  item: number
  project: number
  quantity: number
  status: LotStatus
  priority: Urgency
  target: number
  steps: { machine: number; day: number; start: number; hours: number; done: number }[]
}

const LOTS: LotSpec[] = [
  {
    item: 0, project: 0, quantity: 12, status: 'in_progress', priority: 'high', target: 4,
    steps: [
      { machine: 5, day: -3, start: 6, hours: 3, done: 1 },
      { machine: 2, day: 0, start: 6, hours: 6, done: 0.6 },
      { machine: 1, day: 1, start: 7, hours: 4, done: 0 },
    ],
  },
  {
    item: 1, project: 0, quantity: 40, status: 'in_progress', priority: 'normal', target: 6,
    steps: [
      { machine: 5, day: -2, start: 7, hours: 2, done: 1 },
      { machine: 3, day: 0, start: 6, hours: 7, done: 0.35 },
      { machine: 1, day: 2, start: 6, hours: 3, done: 0 },
    ],
  },
  {
    item: 2, project: 1, quantity: 24, status: 'in_progress', priority: 'normal', target: 5,
    steps: [
      { machine: 4, day: 0, start: 6, hours: 4, done: 0.8 },
      { machine: 1, day: 0, start: 10, hours: 3.5, done: 0 },
    ],
  },
  {
    item: 3, project: 1, quantity: 24, status: 'planned', priority: 'normal', target: 7,
    steps: [
      { machine: 4, day: 1, start: 6, hours: 4, done: 0 },
      { machine: 1, day: 2, start: 9, hours: 3.5, done: 0 },
    ],
  },
  {
    item: 5, project: 2, quantity: 200, status: 'planned', priority: 'low', target: 10,
    steps: [
      { machine: 3, day: 2, start: 6, hours: 8, done: 0 },
    ],
  },
  {
    item: 7, project: 2, quantity: 16, status: 'planned', priority: 'critical', target: 3,
    steps: [
      { machine: 4, day: -1, start: 10, hours: 2, done: 0 },
      { machine: 2, day: 1, start: 6, hours: 5, done: 0 },
    ],
  },
  {
    item: 0, project: 2, quantity: 6, status: 'partially_planned', priority: 'normal', target: 11,
    steps: [
      { machine: 5, day: 0, start: 6, hours: 1.5, done: 0 },
      { machine: 2, day: 4, start: 6, hours: 6, done: 0 },
    ],
  },
  {
    item: 1, project: 1, quantity: 30, status: 'planned', priority: 'high', target: 8,
    steps: [
      { machine: 5, day: 0, start: 8, hours: 2, done: 0 },
      { machine: 3, day: 3, start: 6, hours: 7, done: 0 },
      { machine: 2, day: 5, start: 6, hours: 3, done: 0 },
    ],
  },
]

type OrderStatus = Schemas['ProductionOrderStatus']

function orderStatus(done: number): OrderStatus {
  if (done >= 1) return 'completed'
  return done > 0 ? 'in_progress' : 'queued'
}

const lotNumber = (index: number): string => `L26-${String(412 + index).padStart(4, '0')}`
const orderNumber = (lot: number, step: number): string => `PO26-${String(412 + lot).padStart(4, '0')}-${step + 1}`

export const productionOrders: Schemas['ProductionOrderResponse'][] = []
export const lots: Schemas['LotSummaryResponse'][] = []
export const wipLots: Schemas['WipLotResponse'][] = []

LOTS.forEach((spec, lotIndex) => {
  const item = madeItems[spec.item]!
  const [projectId, projectNumber, customer] = PROJECTS[spec.project]!
  const lotId = 500 + lotIndex
  const positions: Schemas['LotSummaryPositionResponse'][] = []
  const steps: Schemas['LotSummaryStepResponse'][] = []
  const stages: Schemas['WipStageResponse'][] = []

  spec.steps.forEach((step, stepIndex) => {
    const [machineName, , method] = MACHINES[step.machine - 1]!
    const orderId = lotId * 10 + stepIndex
    const positionId = lotId * 10 + stepIndex
    const status = orderStatus(step.done)
    const plannedStart = at(step.day, step.start)
    const plannedEnd = at(step.day, step.start + step.hours)
    const completed = Math.round(spec.quantity * step.done)
    const positionStatus: Schemas['LotPositionStatus'] =
      status === 'completed' ? 'completed' : status === 'in_progress' ? 'in_progress' : 'ordered_or_queued'

    if (status === 'in_progress' || status === 'queued') {
      const list = activeOrders.get(step.machine) ?? []
      list.push({ id: orderId, production_order_number: orderNumber(lotIndex, stepIndex), status })
      activeOrders.set(step.machine, list)
    }

    productionOrders.push({
      id: orderId,
      public_id: uuid(orderId),
      production_order_number: orderNumber(lotIndex, stepIndex),
      status,
      actions: [],
      can_start: status === 'queued',
      lot_id: lotId,
      lot_number: lotNumber(lotIndex),
      lot_position_id: positionId,
      lot_position_sequence: stepIndex + 1,
      lot_position_count: spec.steps.length,
      machine_id: step.machine,
      machine_internal_name: machineName,
      machine_pool_id: null,
      machine_pool_name: '',
      made_item_id: item.id,
      made_item_part_number: item.part_number ?? '',
      made_item_revision: item.revision,
      made_item_material: item.material,
      made_item_mass: item.mass,
      made_item_base_size: null,
      priority: spec.priority,
      quantity: spec.quantity,
      quantity_completed: completed,
      quantity_processed: completed,
      quantity_open: spec.quantity - completed,
      queue_sequence: stepIndex + 1,
      estimated_duration_minutes: Math.round(step.hours * 60),
      planned_start: plannedStart,
      planned_end: plannedEnd,
      planned_end_at_start: null,
      actual_start: status === 'queued' ? null : plannedStart,
      actual_end: status === 'completed' ? plannedEnd : null,
      not_before: null,
      pinned: false,
      waiting_on_raw_material: false,
      edit_version: 0,
      conflicts: [],
      completions: [],
      interruptions: [],
      created_lots: [],
      assessment: null,
      note: null,
      canceled_at: null,
      planned_by_id: 1,
      planned_by: avery,
      started_operator_id: status === 'queued' ? null : 3,
      started_operator: status === 'queued' ? null : people[2]!,
      created: NOW,
      changed: null,
      creator_id: 1,
      creator: avery,
      changed_by_id: null,
      changed_by: null,
    })

    positions.push({
      id: positionId,
      kind: 'internal',
      lead_days: null,
      lead_days_source: null,
      order_id: null,
      order_number: '',
      order_item_id: null,
      order_item_status: '',
      order_item_quantity: null,
      order_item_quantity_delivered: null,
      order_item_items_per_unit: 1,
      order_item_unit: '',
      order_item_closed_short: false,
      order_item_edit_version: 0,
      ordered_by_name: null,
      delivery_date: null,
      delivery_record_count: 0,
      expected_delivery_date: null,
      expected_pickup_date: null,
      planned_delivery_date: null,
      planned_pickup_date: null,
      ready_for_pickup_date: null,
      production_orders: [
        {
          id: orderId,
          status,
          machine_id: step.machine,
          machine_internal_name: machineName,
          machine_pool_id: null,
          machine_pool_name: '',
          planned_start: plannedStart,
          planned_end: plannedEnd,
          actual_start: status === 'queued' ? null : plannedStart,
          actual_end: status === 'completed' ? plannedEnd : null,
          quantity_completed: completed,
          earliest_start_date: null,
          earliest_start_reason: null,
          planned_by_name: avery.full_name,
          conflicts: [],
          edit_version: 0,
        },
      ],
    })

    steps.push({
      id: positionId,
      public_id: uuid(positionId),
      lot_id: lotId,
      position_id: positionId,
      position_kind: 'internal',
      position_status: positionStatus,
      position_needs_machine: true,
      position_quantity: spec.quantity,
      position_quantity_remaining: spec.quantity - completed,
      role: 'fabrication',
      sequence: stepIndex + 1,
      actions: [],
      fabrication_method_id: method,
      fabrication_method_name: fabricationMethods[method - 1]!.name,
      fabrication_method_default_supplier_id: null,
      fabrication_method_required_external: false,
      fabrication_method_requires_machine: true,
      inspection_method_id: null,
      inspection_method_name: null,
      inspection_method_requires_evidence: null,
      estimated_minutes_per_piece: Math.round((step.hours * 60) / spec.quantity),
      estimated_setup_minutes: 30,
      time_budget_per_piece: null,
      source_process_id: null,
      note: null,
      created: NOW,
      creator_id: 1,
    })

    stages.push({
      position_id: positionId,
      sequence: stepIndex + 1,
      kind: 'internal',
      status: positionStatus,
      machine_names: [machineName],
      supplier_name: '',
      quantity: spec.quantity,
      quantity_completed: completed,
    })
  })

  const lot: Schemas['LotSummaryResponse'] = {
    id: lotId,
    public_id: uuid(lotId),
    lot_number: lotNumber(lotIndex),
    status: spec.status,
    priority: spec.priority,
    quantity: spec.quantity,
    quantity_completed: 0,
    quantity_scrapped: 0,
    made_item_id: item.id,
    made_item_part_number: item.part_number ?? '',
    made_item_revision: item.revision,
    made_item_article_name: item.article_name,
    made_item_material: item.material ?? '',
    project_id: projectId,
    project_number: projectNumber,
    project_customer: customer,
    target_date: day(spec.target),
    target_date_source: 'lot',
    target_date_demand_item_id: null,
    required_delivery_date: day(spec.target),
    positions,
    steps,
    actions: [],
    blocked_actions: {},
    demand_status: 'allocated',
    input_demand_id: null,
    is_alteration: false,
    origin_disposition: null,
    origin_lot_id: null,
    replacement_lot_ids: [],
    source_approval_status: 'approved',
    source_approved_by_id: 1,
    source_approved_date: NOW,
    source_bought_item_id: null,
    source_delivery_date: null,
    source_expected_delivery_date: null,
    source_item_id: null,
    source_label: item.material ?? '',
    source_sublabel: '',
    source_made_item_id: null,
    source_material: item.material ?? '',
    source_order_id: null,
    source_order_number: null,
    source_rejected_by_id: null,
    source_rejected_date: null,
    source_rejection_reason: null,
    completed_at: null,
    edit_version: 0,
    created: NOW,
    changed: null,
    creator_id: 1,
    creator: avery,
    changed_by_id: null,
    changed_by: null,
  }
  lots.push(lot)

  if (spec.status === 'in_progress') {
    wipLots.push({
      id: lotId,
      public_id: uuid(lotId),
      lot_number: lot.lot_number,
      status: spec.status,
      priority: spec.priority,
      quantity: spec.quantity,
      made_item_id: item.id,
      made_item_part_number: lot.made_item_part_number,
      made_item_revision: item.revision,
      made_item_article_name: item.article_name,
      finished_count: stages.find((stage) => stage.status === 'in_progress')?.quantity_completed ?? 0,
      raw_count: spec.quantity,
      stages,
    })
  }
})

export const dashboardSummary: Schemas['DashboardSummaryResponse'] = {
  lots: [
    { status: 'in_progress', count: 3 },
    { status: 'planned', count: 4 },
    { status: 'partially_planned', count: 1 },
  ],
  made_demands: [
    { status: 'open', count: 6 },
    { status: 'allocated', count: 14 },
    { status: 'ordered', count: 3 },
    { status: 'fulfilled', count: 31 },
  ],
  bought_demands: [
    { status: 'open', count: 9 },
    { status: 'allocated', count: 7 },
    { status: 'ordered', count: 18 },
    { status: 'fulfilled', count: 52 },
  ],
  source_demands: [
    { status: 'open', count: 2 },
    { status: 'allocated', count: 5 },
    { status: 'ordered', count: 4 },
    { status: 'fulfilled', count: 22 },
  ],
  spend: {
    window_from: day(-29),
    window_to: TODAY,
    order_count: 23,
    net_total: 0,
    days: [],
  },
}

// A month of purchasing with a few busy days, in cents.
const SPEND = [0, 1240, 0, 3890, 820, 0, 0, 5600, 2100, 0, 1480, 760, 0, 0, 9200, 0, 2350, 1100, 640, 0, 0, 4300, 1870, 0, 3150, 980, 0, 0, 6700, 2450]
dashboardSummary.spend.days = SPEND.map((euros, index) => ({ day: day(index - 29), net_total: euros * 100 }))
dashboardSummary.spend.net_total = dashboardSummary.spend.days.reduce((sum, entry) => sum + entry.net_total, 0)

export const todoSources: Schemas['TodoSourcesResponse'] = {
  horizon: day(7),
  lots,
  made_demands: [],
  bought_demands: [],
  source_demands: [],
  orders: [],
  meeting_todos: [],
}

export const productionOperators: Schemas['PublicUserResponse'][] = people.slice(2)

/** The capacity board for the two weeks the pictures show. */
export function scheduleBoard(): Schemas['ScheduleBoardResponse'] {
  const boardOrder = (order: Schemas['ProductionOrderResponse']): Schemas['ScheduleBoardOrderResponse'] => {
    const lot = lots.find((entry) => entry.id === order.lot_id)!
    return {
      order_id: order.id,
      production_order_number: order.production_order_number,
      status: order.status,
      lot_id: order.lot_id,
      lot_number: order.lot_number,
      lot_position_count: order.lot_position_count,
      lot_position_sequence: order.lot_position_sequence,
      made_item_id: order.made_item_id,
      made_item_part_number: order.made_item_part_number,
      made_item_revision: order.made_item_revision,
      project_number: lot.project_number,
      quantity: order.quantity,
      queue_sequence: order.queue_sequence,
      planned_start: order.planned_start,
      planned_end: order.planned_end,
      pinned: false,
      is_floating: false,
      machine_pool_id: null,
      trial_machine_id: null,
      conflicts: [],
    }
  }
  return {
    stale_since: null,
    unassigned: [],
    pools: [],
    machines: MACHINES.map(([internal_name], index) => {
      const machineId = index + 1
      const orders = productionOrders.filter((order) => order.machine_id === machineId && order.status !== 'completed')
      return {
        machine_id: machineId,
        machine_internal_name: internal_name,
        orders: orders.map(boardOrder),
        capacity: Array.from({ length: 14 }, (_, offset) => {
          const date = day(offset)
          const weekday = new Date(`${date}T00:00:00Z`).getUTCDay()
          const available = weekday === 0 || weekday === 6 ? 0 : 480
          const booked = orders
            .filter((order) => order.planned_start?.startsWith(date))
            .reduce((sum, order) => sum + order.estimated_duration_minutes, 0)
          return { date, available_minutes: available, booked_minutes: Math.min(booked, available), overbooked_minutes: Math.max(0, booked - available) }
        }),
      }
    }),
  }
}

/** The detail of one lot, which the timeline and the planning board open per lot. */
export function lotDetail(id: number): Schemas['LotResponse'] | undefined {
  const lot = lots.find((entry) => entry.id === id)
  if (!lot) return undefined
  return {
    ...lot,
    note: null,
    held_at: null,
    canceled_at: null,
    force_completed_at: null,
    origin_lot_number: null,
    follow_up_lots: [],
    steps: lot.steps,
    positions: lot.positions.map((position, index) => {
      const step = lot.steps[index]!
      return {
        ...position,
        lot_id: lot.id,
        public_id: uuid(position.id),
        sequence: step.sequence,
        status: step.position_status,
        quantity: step.position_quantity,
        quantity_completed: step.position_quantity - step.position_quantity_remaining,
        quantity_remaining: step.position_quantity_remaining,
        supplier_name: '',
        steps: [step],
        production_orders: productionOrders.filter((order) => order.lot_position_id === position.id),
        earlier_order_lines: [],
        actions: [],
        note: null,
        created: NOW,
        changed: null,
        creator_id: 1,
        changed_by_id: null,
        changed_by: null,
      }
    }),
  }
}

const NOTIFICATIONS: [string, string, string, number][] = [
  ['pieces_scrapped', 'Pieces scrapped', '2 pieces of L26-0413 were scrapped on LATHE-01: out of tolerance.', 25],
  ['demand_item_fulfilled', 'Demand fulfilled', 'All 24 Motor bracket left for project 26-017 are in stock.', 70],
  ['project_assigned', 'Project assigned', 'Jordan Smith assigned you to project 26-021 Sample Packaging.', 190],
]

export const notifications: Schemas['NotificationsResponse'] = {
  items: NOTIFICATIONS.map(([type, title, message, minutesAgo], index) => ({
    id: index + 1,
    public_id: uuid(4000 + index),
    type,
    title,
    message,
    is_read: false,
    created_at: new Date(Date.parse(NOW) - minutesAgo * 60_000).toISOString(),
    demand_item_id: null,
    meeting_id: null,
    order_id: null,
    product_id: null,
    project_id: null,
  })),
  total: NOTIFICATIONS.length,
  unread_count: NOTIFICATIONS.length,
}

const BOUGHT_ITEMS: [string, string, string, string, Schemas['BoughtItemCatalogueStatus']][] = [
  ['B-000201', 'Deep groove ball bearing 6204-2RS', 'Generic Bearings', '6204-2RS', 'active'],
  ['B-000202', 'Socket head cap screw M8x25', 'Example Fasteners', 'ISO4762-M8X25', 'active'],
  ['B-000203', 'Linear guide rail 20 mm', 'Sample Motion', 'LGR20-800', 'active'],
  ['B-000204', 'Inductive proximity sensor M12', 'Example Sensors', 'PRX-M12-4', 'active'],
  ['B-000205', 'Timing belt pulley T5, 24 teeth', 'Sample Motion', 'T5-24-12', 'inactive'],
  ['B-000206', 'O-ring 32x2.5 NBR', 'Generic Seals', 'OR-32X2.5-NBR', 'active'],
  ['B-000207', 'Spring plunger M6', 'Example Fasteners', 'SP-M6-12', 'replaced'],
]

export const boughtItems: Schemas['BoughtItemWebResponse'][] = BOUGHT_ITEMS.map(
  ([part_number, article_name, manufacturer_name, order_code_1, status], index) => ({
    id: 201 + index,
    public_id: uuid(201 + index),
    part_number,
    revision: null,
    article_name,
    manufacturer_id: 1 + (index % 4),
    manufacturer_name,
    order_code_1,
    order_code_2: null,
    status,
    article_groups: [],
    product_family: null,
    product_family_id: null,
    data_source: 'WEB',
    ean: null,
    gtin: null,
    tariff_number: null,
    mass: null,
    note: null,
    weblink: null,
    pdf_files: [],
    over_delivery_tolerance_percent: null,
    under_delivery_tolerance_percent: null,
    successor_item_id: null,
    edp_part_id: null,
    edp_synced_at: null,
    vault_id: null,
    pdm_file_id: null,
    pdm_file_version: null,
    pdm_locked_fields: [],
    pdm_sync_state: null,
    pdm_synced_at: null,
    archived: false,
    edit_version: 0,
    created: NOW,
    changed: NOW,
    creator_id: 1,
    creator: avery,
    changed_by_id: null,
    changed_by: null,
  }),
)
