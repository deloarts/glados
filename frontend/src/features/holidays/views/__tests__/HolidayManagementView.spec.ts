import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { userWithPermissions } from '@/test-utils/factories'

import type { TenantHoliday } from '../../types/holidayTypes'

const api = vi.hoisted(() => ({
  getTenantHolidays: vi.fn<() => Promise<unknown[]>>(),
  createTenantHoliday: vi.fn<(cmd: unknown) => Promise<unknown>>(),
  updateTenantHoliday: vi.fn<(id: number, cmd: unknown) => Promise<unknown>>(),
  deleteTenantHoliday: vi.fn<(id: number) => Promise<void>>(),
}))

vi.mock('../../api/holidaysApi', () => api)

import HolidayManagementView from '../HolidayManagementView.vue'

const SHUTDOWN: TenantHoliday = {
  id: 1,
  public_id: '11111111-1111-1111-1111-111111111111',
  created: '2026-01-01',
  changed: null,
  changed_by: null,
  changed_by_id: null,
  name: 'Summer shutdown',
  category: 'plant_shutdown',
  start_date: '2026-08-03',
  end_date: '2026-08-14',
  creator_id: 1,
}

async function mountTab(permissions: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  const wrapper = mountWithApp(HolidayManagementView, {
    pinia,
    attachTo: document.body,
    global: { plugins: [ConfirmationService] },
  })
  await flushPromises()
  return wrapper
}

function button(wrapper: Awaited<ReturnType<typeof mountTab>>, labelKey: string) {
  const label = i18n.global.t(labelKey) as string
  return wrapper.findAllComponents({ name: 'Button' }).find((b) => b.props('label') === label)!
}

describe('HolidayManagementView', () => {
  beforeEach(() => {
    api.getTenantHolidays.mockReset()
    api.createTenantHoliday.mockReset()
    api.getTenantHolidays.mockResolvedValue([SHUTDOWN])
    api.createTenantHoliday.mockResolvedValue(SHUTDOWN)
  })

  it('lists each holiday with its category and its number of days', async () => {
    const wrapper = await mountTab(['write:machines'])

    const row = wrapper.find('tbody tr')
    expect(row.text()).toContain('Summer shutdown')
    expect(row.text()).toContain(i18n.global.t('resources.holidays.categories.plant_shutdown'))
    expect(row.text()).toContain('12')

    wrapper.unmount()
  })

  it('shows Add disabled to a user who may not change machines', async () => {
    const wrapper = await mountTab([])

    const add = button(wrapper, 'resources.holidays.add')
    expect((add.element as HTMLButtonElement).disabled).toBe(true)
    expect(
      (add.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null)
        ?.$_ptooltipValue,
    ).toBe('This needs the permission Write Production Machines.')

    wrapper.unmount()
  })

  it('offers Edit and Delete to a user who may write machines', async () => {
    const wrapper = await mountTab(['write:machines'])

    const rowButtons = wrapper.find('tbody tr').findAll('button')
    const edit = rowButtons.find((b) => b.attributes('aria-label') === i18n.global.t('resources.holidays.edit'))!
    const remove = rowButtons.find((b) => b.attributes('aria-label') === i18n.global.t('common.delete'))!
    expect((edit.element as HTMLButtonElement).disabled).toBe(false)
    expect((remove.element as HTMLButtonElement).disabled).toBe(false)

    wrapper.unmount()
  })

  it('saves a single day holiday with its start as its end', async () => {
    const wrapper = await mountTab(['write:machines'])
    await button(wrapper, 'resources.holidays.add').trigger('click')
    await flushPromises()

    const header = i18n.global.t('resources.holidays.add')
    const dialog = wrapper
      .findAllComponents({ name: 'Dialog' })
      .find((d) => d.props('header') === header)!
    await dialog.findComponent({ name: 'InputText' }).setValue('National Day')
    const pickers = dialog.findAllComponents({ name: 'DatePicker' })
    pickers[0]!.vm.$emit('update:modelValue', new Date(2026, 9, 26))
    await flushPromises()
    await button(wrapper, 'common.save').trigger('click')
    await flushPromises()

    expect(api.createTenantHoliday).toHaveBeenCalledWith({
      name: 'National Day',
      category: 'public_holiday',
      start_date: '2026-10-26',
      end_date: '2026-10-26',
    })

    wrapper.unmount()
  })
})
