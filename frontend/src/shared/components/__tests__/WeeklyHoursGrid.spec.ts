import { describe, expect, it } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { WeeklyHours } from '@/shared/utils/weeklyHours'

import WeeklyHoursGrid from '../WeeklyHoursGrid.vue'

function week(): WeeklyHours {
  return {
    0: [{ start: '08:00', minutes: 480 }],
    1: [
      { start: '06:00', minutes: 240 },
      { start: '14:00', minutes: 240 },
    ],
    2: [],
    3: [{ start: '22:00', minutes: 480 }],
    4: [{ start: '08:00', minutes: 480 }],
    5: [],
    6: [],
  }
}

function mountGrid(hours: WeeklyHours) {
  const updates: WeeklyHours[] = []
  const wrapper = mountWithApp(WeeklyHoursGrid, {
    props: {
      hours,
      'onUpdate:hours': (value: WeeklyHours) => updates.push(value),
    },
  })
  return { wrapper, updates }
}

describe('WeeklyHoursGrid', () => {
  it('shows each day with the local start of its first interval', () => {
    const { wrapper } = mountGrid(week())

    const starts = wrapper
      .findAll('input[type="time"]')
      .map((input) => (input.element as HTMLInputElement).value)
    expect(starts).toEqual(['08:00', '06:00', '08:00', '22:00', '08:00', '08:00', '08:00'])
    expect(wrapper.text()).toContain('+1')

    wrapper.unmount()
  })

  it('changes the start of the first interval and keeps the second', async () => {
    const { wrapper, updates } = mountGrid(week())

    await wrapper.findAll('input[type="time"]')[1]!.setValue('05:30')

    expect(updates.at(-1)?.[1]).toEqual([
      { start: '05:30', minutes: 240 },
      { start: '14:00', minutes: 240 },
    ])

    wrapper.unmount()
  })

  it('opens a closed day with one default interval and closes it again', async () => {
    const { wrapper, updates } = mountGrid(week())
    const closedBoxes = wrapper.findAllComponents({ name: 'Checkbox' })

    closedBoxes[2]!.vm.$emit('update:modelValue', false)
    expect(updates.at(-1)?.[2]).toEqual([{ start: '08:00', minutes: 480 }])

    closedBoxes[0]!.vm.$emit('update:modelValue', true)
    expect(updates.at(-1)?.[0]).toEqual([])

    wrapper.unmount()
  })
})
