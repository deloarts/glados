import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { userWithPermissions } from '@/test-utils/factories'
import { useAdminSettingsStore } from '@/features/admin-settings'

import type { AdminPlanningSettings, AllAdminSettings } from '@/features/admin-settings'

const putMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    put: (url: string, payload: unknown) => putMock(url, payload),
  },
}))

import AdminSettingsTabPlanning from '../AdminSettingsTabPlanning.vue'

function makePlanningSettings(
  overrides: Partial<AdminPlanningSettings> = {},
): AdminPlanningSettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    commit_horizon_working_days: 5,
    plan_retention_days: 400,
    booking_quality_since: '2026-11-27T08:00:00Z',
    ...overrides,
  }
}

async function mountTab(permissions: string[], planning: AdminPlanningSettings) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  useAdminSettingsStore().settings = { planning } as unknown as AllAdminSettings

  const wrapper = mountWithApp(AdminSettingsTabPlanning, { pinia, attachTo: document.body })
  await flushPromises()
  return wrapper
}

function input(wrapper: ReturnType<typeof mount>, labelKey: string) {
  const label = i18n.global.t(labelKey) as string
  const row = wrapper
    .findAll('.field-row')
    .find((r) => r.find('label').exists() && r.find('label').text().startsWith(label))
  return row!.findComponent({ name: 'InputNumber' })
}

function saveButton(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (i18n.global.t('common.save') as string))!
}

describe('AdminSettingsTabPlanning', () => {
  beforeEach(() => {
    putMock.mockReset()
  })

  it('shows the stored horizon, retention and the start of the booking quality view', async () => {
    const wrapper = await mountTab(
      ['write:settings'],
      makePlanningSettings({ commit_horizon_working_days: 7, plan_retention_days: 365 }),
    )

    expect(input(wrapper, 'adminSettings.planning.commitHorizonWorkingDays').props('modelValue')).toBe(7)
    expect(input(wrapper, 'adminSettings.planning.planRetentionDays').props('modelValue')).toBe(365)
    expect(wrapper.text()).toContain(i18n.global.t('adminSettings.planning.bookingQualitySince'))
    expect(wrapper.text()).toContain('2026')

    wrapper.unmount()
  })

  it('sends both numbers on save and never the booking quality start', async () => {
    putMock.mockResolvedValue({ data: makePlanningSettings({ commit_horizon_working_days: 10 }) })
    const wrapper = await mountTab(['write:settings'], makePlanningSettings())

    await input(wrapper, 'adminSettings.planning.commitHorizonWorkingDays').vm.$emit(
      'update:modelValue',
      10,
    )
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith('/admin/settings/planning', {
      commit_horizon_working_days: 10,
      plan_retention_days: 400,
    })

    wrapper.unmount()
  })

  it('is disabled without write:settings', async () => {
    const wrapper = await mountTab(['read:settings'], makePlanningSettings())

    expect(input(wrapper, 'adminSettings.planning.commitHorizonWorkingDays').props('disabled')).toBe(true)
    expect(saveButton(wrapper).attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })
})
