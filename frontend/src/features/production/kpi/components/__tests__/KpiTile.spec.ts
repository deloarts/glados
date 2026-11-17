import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import KpiTile from '../KpiTile.vue'

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

describe('KpiTile', () => {
  it('renders the formatted value and label', () => {
    const wrapper = mountWithApp(KpiTile, {
      props: {
        label: 'Schedule Adherence',
        definition: 'Some ISO 22400 definition.',
        value: 0.824,
        formatValue: percent,
      },
    })

    expect(wrapper.text()).toContain('Schedule Adherence')
    expect(wrapper.text()).toContain('82.4%')
  })

  it('renders an explicit n/a state with its reason when value is null', () => {
    const wrapper = mountWithApp(KpiTile, {
      props: {
        label: 'Schedule Adherence',
        definition: 'Some ISO 22400 definition.',
        value: null,
        formatValue: percent,
        naReason: 'No completed orders with a baseline in this period.',
      },
    })

    expect(wrapper.text()).not.toContain('82.4%')
    expect(wrapper.text()).toContain('No completed orders with a baseline in this period.')
  })

  it('shows a favorable "up" delta when the value rose and higherIsBetter is true', () => {
    const wrapper = mountWithApp(KpiTile, {
      props: {
        label: 'Schedule Adherence',
        definition: 'x',
        value: 0.9,
        previousValue: 0.8,
        formatValue: percent,
        higherIsBetter: true,
      },
    })

    expect(wrapper.text()).toContain('+10.0%')
    expect(wrapper.find('.kpi-tile-delta--favorable').exists()).toBe(true)
    expect(wrapper.find('.kpi-tile-delta--unfavorable').exists()).toBe(false)
  })

  it('shows an unfavorable "up" delta when higherIsBetter is false (e.g. scrap ratio)', () => {
    const wrapper = mountWithApp(KpiTile, {
      props: {
        label: 'Scrap Ratio',
        definition: 'x',
        value: 0.1,
        previousValue: 0.05,
        formatValue: percent,
        higherIsBetter: false,
      },
    })

    expect(wrapper.text()).toContain('+5.0%')
    expect(wrapper.find('.kpi-tile-delta--unfavorable').exists()).toBe(true)
    expect(wrapper.find('.kpi-tile-delta--favorable').exists()).toBe(false)
  })

  it('renders no delta chip when there is no previous value to compare against', () => {
    const wrapper = mountWithApp(KpiTile, {
      props: {
        label: 'Schedule Adherence',
        definition: 'x',
        value: 0.9,
        formatValue: percent,
      },
    })

    expect(wrapper.find('.kpi-tile-delta').exists()).toBe(false)
  })

  it('treats a floating-point-noise difference as flat, not up or down', () => {
    const wrapper = mountWithApp(KpiTile, {
      props: {
        label: 'Schedule Adherence',
        definition: 'x',
        value: 0.1 + 0.2, // 0.30000000000000004
        previousValue: 0.3,
        formatValue: percent,
      },
    })

    expect(wrapper.find('.kpi-tile-delta--favorable').exists()).toBe(false)
    expect(wrapper.find('.kpi-tile-delta--unfavorable').exists()).toBe(false)
    expect(wrapper.find('.kpi-tile-delta').exists()).toBe(true)
  })
})
