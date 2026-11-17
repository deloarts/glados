import { describe, it, expect, afterEach } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import SpendLineChart from '../SpendLineChart.vue'

function makePoints() {
  return [{ day: 1, cumulative: 1234, date: new Date(2026, 7, 6) }]
}

// The real OpenVue Chart needs a canvas rendering context jsdom doesn't
// provide, so it is stubbed here (named, so findComponent can still reach
// it) purely to capture the `options` prop the component computed.
const chartStub = {
  name: 'Chart',
  props: ['data', 'options', 'type'],
  template: '<div class="chart-stub" />',
}

function mountChart() {
  return mountWithApp(SpendLineChart, {
    props: { points: makePoints() },
    global: { stubs: { Chart: chartStub } },
  })
}

function tooltipLabel(wrapper: ReturnType<typeof mountChart>): string {
  const chart = wrapper.findComponent({ name: 'Chart' })
  const options = chart.props('options') as {
    plugins: { tooltip: { callbacks: { label: (item: { parsed: { y: number } }) => string } } }
  }
  return options.plugins.tooltip.callbacks.label({ parsed: { y: 1234 } })
}

// The default `formatValue` must format numbers per the active locale,
// rather than through a bare `Math.round(value).toLocaleString()`, which
// always reads as English-formatted regardless of the UI language the user
// picked in Glados.
describe('SpendLineChart', () => {
  afterEach(() => {
    i18n.global.locale.value = 'enGB'
  })

  it('uses a comma thousands separator for en-GB by default', () => {
    expect(tooltipLabel(mountChart())).toBe('1,234')
  })

  it('uses a non-breaking-space thousands separator for de-AT, not the browser default', () => {
    i18n.global.locale.value = 'deAT'

    // Intl's de-AT grouping separator is U+00A0 (non-breaking space), not a
    // regular space or a period.
    expect(tooltipLabel(mountChart())).toBe('1 234')
  })
})
