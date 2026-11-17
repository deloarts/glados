import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'

import DeliveriesExpectedWidget from '../components/widgets/DeliveriesExpectedWidget.vue'
import MachineBoardWidget from '../components/widgets/MachineBoardWidget.vue'
import MachineDetailWidget from '../components/widgets/MachineDetailWidget.vue'
import ProductsWidget from '../components/widgets/ProductsWidget.vue'
import ProjectsWidget from '../components/widgets/ProjectsWidget.vue'
import WeatherWidget from '../components/widgets/WeatherWidget.vue'
import type {
  InfoscreenDeliveryRow,
  WidgetConfigOf,
  WidgetDataOf,
} from '../types/infoscreenFeed'
import { weatherIcon, weatherKind } from '../utils/weatherCodes'
import { orderCardFixture } from './infoscreenFixtures'

const NOW = new Date('2026-11-10T10:00:00Z')

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] })
  vi.setSystemTime(NOW)
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('machine board cards', () => {
  it('show the lot number, part number and article name, and no times', () => {
    const w = mountWithApp(MachineBoardWidget, {
      props: {
        config: { type: 'machine_board', title: null, machine_ids: [1], pool_ids: [], next_count: 3 },
        data: {
          type: 'machine_board',
          machines: [
            {
              machine_id: 1,
              machine_name: 'Laser 1',
              state: 'running',
              downtime_reason: null,
              current: orderCardFixture(),
              next: [orderCardFixture({ production_order_id: 12, lot_number: 'L-2026-0043' })],
            },
          ],
          pools: [],
        } as WidgetDataOf<'machine_board'>,
      },
    })

    const current = w.get('[data-testid="machine-current"] [data-testid="order-card-text"]')
    expect(current.findAll('.order-card-line').map((line) => line.text())).toEqual([
      'L-2026-0042',
      'P-100',
      'Bracket',
    ])
    const next = w.get('[data-testid="machine-next"] [data-testid="order-card-text"]')
    expect(next.findAll('.order-card-line')).toHaveLength(3)
    expect(w.text()).not.toMatch(/\d{2}:\d{2}/)
  })
})

function delivery(overrides: Partial<InfoscreenDeliveryRow>): InfoscreenDeliveryRow {
  return {
    order_number: 'PO-1',
    part_number: 'B-1',
    item_name: 'Bolt',
    quantity: 4,
    unit: 'pcs',
    supplier_name: 'Bolts Ltd',
    expected_date: '2026-11-10',
    days_late: null,
    thumbnail_url: null,
    ...overrides,
  } as InfoscreenDeliveryRow
}

describe('deliveries expected', () => {
  it('groups overdue, today, tomorrow and later days, today standing out', () => {
    const w = mountWithApp(DeliveriesExpectedWidget, {
      props: {
        config: { type: 'deliveries_expected', title: null, horizon_days: 7, show_overdue: true },
        data: {
          type: 'deliveries_expected',
          deliveries: [
            delivery({ expected_date: '2026-11-08', days_late: 2 }),
            delivery({ expected_date: '2026-11-10' }),
            delivery({ expected_date: '2026-11-10', order_number: 'PO-2' }),
            delivery({ expected_date: '2026-11-11' }),
            delivery({ expected_date: '2026-11-13' }),
          ],
        } as WidgetDataOf<'deliveries_expected'>,
      },
    })

    const groups = w.findAll('[data-testid="delivery-group"]')
    expect(groups.map((g) => g.get('h3').text())).toEqual([
      'Overdue 1',
      'Today 2',
      'Tomorrow 1',
      expect.stringContaining('Friday'),
    ])
    expect(groups[1]!.classes()).toContain('delivery-group--today')
    expect(groups[0]!.text()).toContain('2 days late')
  })
})

const weatherConfig: WidgetConfigOf<'weather'> = {
  type: 'weather',
  title: null,
  location_name: 'Zell am See',
  region: 'Salzburg',
  country_code: 'AT',
  latitude: 47.32,
  longitude: 12.8,
  days: 2,
  show_wind: true,
}

function weatherData(overrides: Partial<WidgetDataOf<'weather'>> = {}): WidgetDataOf<'weather'> {
  return {
    type: 'weather',
    status: 'ok',
    location_name: 'Zell am See',
    region: 'Salzburg',
    now: { temperature: 3.6, symbol: 'rain', wind_speed: 12.4, is_day: true },
    days: [
      { date: '2026-11-10', symbol: 'rain', temperature_max: 6, temperature_min: 1, precipitation_mm: 4.2 },
      { date: '2026-11-11', symbol: 'clearsky_day', temperature_max: 8, temperature_min: -1, precipitation_mm: 0 },
      { date: '2026-11-12', symbol: 'cloudy', temperature_max: 7, temperature_min: 2, precipitation_mm: null },
    ],
    fetched_at: '2026-11-10T09:50:00Z',
    attribution: 'MET Norway',
    ...overrides,
  } as WidgetDataOf<'weather'>
}

describe('weather', () => {
  it('shows now, the wind and the days after today', () => {
    const w = mountWithApp(WeatherWidget, { props: { config: weatherConfig, data: weatherData() } })

    expect(w.text()).toContain('Zell am See, Salzburg')
    expect(w.get('[data-testid="weather-now"]').text()).toContain('4°')
    expect(w.get('[data-testid="weather-now"]').text()).toContain('Rain')
    expect(w.get('[data-testid="weather-now"]').text()).toContain('4.2 mm')
    expect(w.get('[data-testid="weather-wind"]').text()).toContain('12 km/h')
    expect(w.get('[data-testid="weather-credit"]').text()).toBe('Data: MET Norway')
    const days = w.findAll('[data-testid="weather-day"]')
    expect(days).toHaveLength(2)
    expect(days[0]!.text()).toContain('Tomorrow')
    expect(w.find('[data-testid="weather-stale"]').exists()).toBe(false)
  })

  it('says how old a forecast is that stands in', () => {
    const w = mountWithApp(WeatherWidget, {
      props: { config: weatherConfig, data: weatherData({ fetched_at: '2026-11-10T07:00:00Z' }) },
    })
    expect(w.get('[data-testid="weather-stale"]').text()).toMatch(/^As of \d{2}:\d{2}$/)
  })

  it('says when the weather is off or unavailable', () => {
    const off = mountWithApp(WeatherWidget, {
      props: { config: weatherConfig, data: weatherData({ status: 'off', now: null, days: [] }) },
    })
    expect(off.get('[data-testid="weather-off"]').text()).toBe('The weather is switched off')

    const down = mountWithApp(WeatherWidget, {
      props: {
        config: weatherConfig,
        data: weatherData({ status: 'unavailable', now: null, days: [] }),
      },
    })
    expect(down.get('[data-testid="weather-unavailable"]').text()).toBe('No weather data')
  })

  it('maps the weather symbols to kinds and night icons', () => {
    expect(weatherKind('clearsky_day')).toBe('clear')
    expect(weatherKind('fair_night')).toBe('partlyCloudy')
    expect(weatherKind('lightrain')).toBe('drizzle')
    expect(weatherKind('heavyrainshowers_polartwilight')).toBe('showers')
    expect(weatherKind('lightsleetshowers_day')).toBe('sleet')
    expect(weatherKind('heavysnowshowers_day')).toBe('snowShowers')
    expect(weatherKind('snow')).toBe('snow')
    expect(weatherKind('rainshowersandthunder_day')).toBe('thunderstorm')
    expect(weatherKind(null)).toBe('unknown')
    expect(weatherIcon('clearsky_night')).toBe('mdi-weather-night')
    expect(weatherIcon('rain')).toBe('mdi-weather-rainy')
  })
})

describe('products and projects', () => {
  it('lists the products with their projects only when asked', () => {
    const data = {
      type: 'products',
      products: [
        {
          product_id: 1,
          product_number: 'M-200',
          designation: 'Press line',
          description: null,
          machine_type: 'Press',
          customer_name: null,
          projects: [{ project_id: 4, project_number: 'P-2', description: 'Retrofit' }],
        },
      ],
    } as WidgetDataOf<'products'>
    const withProjects = mountWithApp(ProductsWidget, {
      props: {
        config: { type: 'products', title: null, show_projects: true, show_customer: false },
        data,
      },
    })
    expect(withProjects.get('[data-testid="product-row"]').text()).toContain('Press line')
    expect(withProjects.findAll('[data-testid="product-project"]')).toHaveLength(1)

    const without = mountWithApp(ProductsWidget, {
      props: {
        config: { type: 'products', title: null, show_projects: false, show_customer: false },
        data,
      },
    })
    expect(without.findAll('[data-testid="product-project"]')).toHaveLength(0)
  })

  it('lists the projects with their product', () => {
    const w = mountWithApp(ProjectsWidget, {
      props: {
        config: { type: 'projects', title: null, show_customer: false },
        data: {
          type: 'projects',
          projects: [
            {
              project_id: 4,
              project_number: 'P-2',
              description: 'Retrofit',
              product_number: 'M-200',
              product_designation: 'Press line',
              customer_name: null,
            },
          ],
        } as WidgetDataOf<'projects'>,
      },
    })
    expect(w.get('[data-testid="project-row"]').text()).toContain('P-2')
    expect(w.get('[data-testid="project-row"]').text()).toContain('M-200 · Press line')
  })
})

function machineDetailData(
  overrides: Partial<WidgetDataOf<'machine_detail'>> = {},
): WidgetDataOf<'machine_detail'> {
  return {
    type: 'machine_detail',
    machine_id: 1,
    machine_name: 'Lathe',
    state: 'running',
    downtime_reason: null,
    order: {
      production_order_id: 11,
      current: true,
      status: 'in_progress',
      lot_number: 'L-2026-0042',
      part_number: 'MD-100',
      item_name: 'Shaft',
      revision: 'B',
      material: '1.0503',
      mass_grams: 850,
      base_size: null,
      quantity: 10,
      quantity_completed: 4,
      step_sequence: 2,
      step_count: 5,
      picture_url: '/api/v1/web/terminal-device/thumbnails/image-token',
      drawing_url: '/api/v1/web/terminal-device/drawings/drawing-token',
      raw_material: {
        kind: 'source',
        part_number: null,
        name: 'Round bar',
        material: '1.0503',
        dimension: 'Ø40',
        demand_status: 'ordered',
        expected_delivery: '2026-11-12',
      },
      lot: {
        lot_id: 3,
        lot_number: 'L-2026-0042',
        status: 'in_progress',
        quantity: 10,
        project_number: 'P-MD-1',
        customer_name: null,
      },
    },
    next: [orderCardFixture({ production_order_id: 12, lot_number: 'L-2026-0043' })],
    ...overrides,
  } as WidgetDataOf<'machine_detail'>
}

const detailConfig: WidgetConfigOf<'machine_detail'> = {
  type: 'machine_detail',
  title: null,
  machine_id: 1,
  next_count: 3,
  show_drawing: true,
  show_customer: false,
}

describe('machine detail', () => {
  it('shows the order with its facts, raw material and the drawing embedded', async () => {
    type DrawingResponse = { ok: boolean; status: number; blob: () => Promise<Blob> }
    const fetchMock = vi.fn<(url: string) => Promise<DrawingResponse>>(async () => ({
      ok: true,
      status: 200,
      blob: async () => new Blob(['%PDF'], { type: 'application/pdf' }),
    }))
    vi.stubGlobal('fetch', fetchMock)
    const createObjectURL = vi.fn<(blob: Blob) => string>(() => 'blob:drawing')
    const revokeObjectURL = vi.fn<(url: string) => void>()
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL, revokeObjectURL }))

    const w = mountWithApp(MachineDetailWidget, {
      props: { config: detailConfig, data: machineDetailData() },
    })
    await flushPromises()

    expect(w.text()).toContain('Lathe')
    const order = w.get('[data-testid="machine-detail-order"]')
    expect(order.findAll('.order-card-line').map((line) => line.text())).toEqual([
      'L-2026-0042',
      'MD-100',
      'Shaft',
    ])
    expect(order.text()).toContain('4 / 10')
    expect(order.text()).toContain('2 of 5')
    expect(order.text()).toContain('P-MD-1')
    expect(w.get('[data-testid="machine-detail-raw"]').text()).toContain('Round bar')
    expect(w.get('[data-testid="machine-detail-raw"]').text()).toContain('Ordered')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/web/terminal-device/drawings/drawing-token'),
    )
    expect(w.get('[data-testid="machine-detail-drawing"]').attributes('src')).toBe(
      'blob:drawing#view=Fit&zoom=page-fit',
    )
    expect(w.findAll('[data-testid="machine-detail-next"]')).toHaveLength(1)
  })

  it('names the next order when the machine is free and says when the machine is gone', () => {
    const data = machineDetailData()
    const free = mountWithApp(MachineDetailWidget, {
      props: {
        config: detailConfig,
        data: { ...data, order: { ...data.order!, current: false, drawing_url: null } },
      },
    })
    expect(free.get('[data-testid="machine-detail-order"]').text()).toContain('Next')
    expect(free.find('[data-testid="machine-detail-drawing"]').exists()).toBe(false)

    const gone = mountWithApp(MachineDetailWidget, {
      props: {
        config: detailConfig,
        data: machineDetailData({ machine_name: null, state: null, order: null, next: [] }),
      },
    })
    expect(gone.get('[data-testid="machine-detail-missing"]').text()).toBe(
      'This machine no longer exists',
    )
  })
})
