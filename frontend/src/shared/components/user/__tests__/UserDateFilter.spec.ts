import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeUserResponse } from '@/test-utils/factories'

vi.mock('@/core/api/users/getUserDirectory', () => ({
  getUserDirectory: async () => ({
    items: [
      makeUserResponse({ id: 3, full_name: 'Ada Admin' }),
      makeUserResponse({ id: 4, full_name: 'Bob Builder' }),
    ],
    total: 2,
  }),
}))

import { formatISODate } from '@/core/utils/dates'
import UserDateFilter from '../UserDateFilter.vue'

type Range = [Date, Date | null] | null

const mounted: Array<{ unmount: () => void }> = []

async function mountFilter(
  props: {
    userId?: number | null
    userIds?: number[]
    range?: Range
    placeholder?: string
    userOnly?: boolean
  } = {},
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(UserDateFilter, {
    pinia,
    attachTo: document.body,
    props: { column: 'Created', ...props },
  })
  mounted.push(wrapper)
  await flushPromises()
  return wrapper
}

function field(wrapper: Awaited<ReturnType<typeof mountFilter>>): HTMLInputElement {
  return wrapper.get('[data-testid="user-date-filter-field"]').element as HTMLInputElement
}

afterEach(() => {
  mounted.splice(0).forEach((wrapper) => wrapper.unmount())
})

describe('UserDateFilter', () => {
  it('shows the placeholder and no clear icon while nothing is set', async () => {
    const wrapper = await mountFilter({ placeholder: 'Any' })
    expect(field(wrapper).value).toBe('')
    expect(field(wrapper).placeholder).toBe('Any')
    expect(wrapper.find('[data-testid="user-date-filter-clear"]').exists()).toBe(false)
  })

  it('sums up the person and the date range', async () => {
    const from = new Date(2026, 9, 1)
    const to = new Date(2026, 9, 15)
    const wrapper = await mountFilter({ userId: 3, range: [from, to] })
    expect(field(wrapper).value).toBe(
      `Ada Admin, ${formatISODate('2026-10-01')} to ${formatISODate('2026-10-15')}`,
    )
  })

  it('sums up a range that has a start only', async () => {
    const wrapper = await mountFilter({ range: [new Date(2026, 9, 1), null] })
    expect(field(wrapper).value).toBe(`from ${formatISODate('2026-10-01')}`)
  })

  it('clears the person and the range together', async () => {
    const wrapper = await mountFilter({ userId: 3, range: [new Date(2026, 9, 1), null] })
    await wrapper.get('[data-testid="user-date-filter-clear"]').trigger('click')
    expect(wrapper.emitted('update:userId')?.at(-1)).toEqual([null])
    expect(wrapper.emitted('update:range')?.at(-1)).toEqual([null])
  })

  it('opens a panel with the user select above the date range picker', async () => {
    const wrapper = await mountFilter()
    await wrapper.get('[data-testid="user-date-filter-field"]').trigger('click')
    await flushPromises()

    const panel = document.body.querySelector('[data-testid="user-date-filter-panel"]')
    expect(panel).not.toBeNull()
    const select = wrapper.findComponent({ name: 'Select' })
    expect(select.props('options')).toHaveLength(2)
    expect(select.props('filter')).toBe(true)
    expect(wrapper.findComponent({ name: 'DatePicker' }).props('selectionMode')).toBe('range')
  })

  it('writes the picked person and the picked range to their own models', async () => {
    const wrapper = await mountFilter()
    await wrapper.get('[data-testid="user-date-filter-field"]').trigger('click')
    await flushPromises()

    await wrapper.findComponent({ name: 'Select' }).vm.$emit('update:modelValue', 4)
    expect(wrapper.emitted('update:userId')?.at(-1)).toEqual([4])

    const from = new Date(2026, 9, 1)
    await wrapper.findComponent({ name: 'DatePicker' }).vm.$emit('update:modelValue', [from, null])
    expect(wrapper.emitted('update:range')?.at(-1)).toEqual([[from, null]])

    await wrapper.findComponent({ name: 'DatePicker' }).vm.$emit('update:modelValue', null)
    expect(wrapper.emitted('update:range')?.at(-1)).toEqual([null])
  })

  it('leaves out the date range picker for a user only filter', async () => {
    const wrapper = await mountFilter({ userOnly: true })
    await wrapper.get('[data-testid="user-date-filter-field"]').trigger('click')
    await flushPromises()

    expect(wrapper.findComponent({ name: 'Select' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'DatePicker' }).exists()).toBe(false)
  })

  it('picks several people when the ids are bound as a list', async () => {
    const wrapper = await mountFilter({ userIds: [3, 4] })
    expect(field(wrapper).value).toBe('Ada Admin, Bob Builder')

    await wrapper.get('[data-testid="user-date-filter-field"]').trigger('click')
    await flushPromises()
    expect(wrapper.findComponent({ name: 'MultiSelect' }).exists()).toBe(true)
    await wrapper.findComponent({ name: 'MultiSelect' }).vm.$emit('update:modelValue', [4])
    expect(wrapper.emitted('update:userIds')?.at(-1)).toEqual([[4]])

    await wrapper.get('[data-testid="user-date-filter-clear"]').trigger('click')
    expect(wrapper.emitted('update:userIds')?.at(-1)).toEqual([[]])
    expect(wrapper.emitted('update:userId')).toBeUndefined()
  })
})
