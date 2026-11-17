import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import KpiScrapByReasonChart from '../KpiScrapByReasonChart.vue'

import type { ScrapByReasonRowResult } from '../../types/productionKpiResponse'

// The real OpenVue Chart needs a canvas rendering context jsdom doesn't
// provide, so it is stubbed here (named, so findComponent can still reach
// it) purely to capture the `data`/`options` props the component computed,
// mirroring SpendLineChart.spec.ts's own stub.
const chartStub = {
  name: 'Chart',
  props: ['data', 'options', 'type'],
  template: '<div class="chart-stub" />',
}

function makeRows(): ScrapByReasonRowResult[] {
  return [
    { reason: 'tool_breakage', quantity: 3, share: { value: 0.75, numerator: 3, denominator: 4 } },
    { reason: 'material_defect', quantity: 1, share: { value: 0.25, numerator: 1, denominator: 4 } },
  ]
}

function mountChart(rows: ScrapByReasonRowResult[]) {
  return mountWithApp(KpiScrapByReasonChart, {
    props: { rows },
    global: { stubs: { Chart: chartStub } },
  })
}

describe('KpiScrapByReasonChart', () => {
  it('renders an empty state when there are no rows', () => {
    const wrapper = mountChart([])
    expect(wrapper.findComponent({ name: 'Chart' }).exists()).toBe(false)
    expect(wrapper.text()).toContain('No scrapped or rejected pieces in this period.')
  })

  it('renders a horizontal bar chart with one label per reason, translated', () => {
    const wrapper = mountChart(makeRows())
    const chart = wrapper.findComponent({ name: 'Chart' })
    expect(chart.exists()).toBe(true)
    expect(chart.props('type')).toBe('bar')

    const data = chart.props('data') as { labels: string[]; datasets: { data: number[] }[] }
    expect(data.labels).toEqual(['Tool Breakage', 'Material Defect'])
    expect(data.datasets[0]?.data).toEqual([3, 1])

    const options = chart.props('options') as { indexAxis: string }
    expect(options.indexAxis).toBe('y')
  })

  it('formats the tooltip label with quantity and share', () => {
    const wrapper = mountChart(makeRows())
    const chart = wrapper.findComponent({ name: 'Chart' })
    const options = chart.props('options') as {
      plugins: {
        tooltip: { callbacks: { label: (item: { dataIndex: number; parsed: { x: number } }) => string } }
      }
    }
    const label = options.plugins.tooltip.callbacks.label({ dataIndex: 0, parsed: { x: 3 } })
    expect(label).toBe('3 (75.0%)')
  })

  it('falls back to the raw reason string for an unrecognized backend value', () => {
    const wrapper = mountChart([
      { reason: 'unheard_of', quantity: 1, share: { value: 1, numerator: 1, denominator: 1 } },
    ])
    const chart = wrapper.findComponent({ name: 'Chart' })
    const data = chart.props('data') as { labels: string[] }
    expect(data.labels).toEqual(['unheard_of'])
  })
})
