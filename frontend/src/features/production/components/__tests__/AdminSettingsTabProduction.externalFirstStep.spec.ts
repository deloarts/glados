import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { userWithPermissions } from '@/test-utils/factories'
import { useAdminSettingsStore } from '@/features/admin-settings'

import type { AdminProductionSettings, AllAdminSettings } from '@/features/admin-settings'

// Mirrors AdminSettingsTabProduction.materialAssignment.spec.ts's mount and
// store seeding. This covers the Material Approval toggle that decides
// whether a lot whose first position a supplier does needs no material:
// external_first_step_needs_no_material.

const putMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: vi
      .fn<() => Promise<unknown>>()
      .mockResolvedValue({ data: { items: [], total: 0, limit: 1000, skip: 0 } }),
    put: (url: string, payload: unknown) => putMock(url, payload),
  },
}))

import AdminSettingsTabProduction from '../AdminSettingsTabProduction.vue'

function makeProductionSettings(
  overrides: Partial<AdminProductionSettings> = {},
): AdminProductionSettings {
  return {
    frozen_window_hours: 0,
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    production_order_number_format: 'PO-{n}',
    default_weekly_hours: {},
    default_external_lead_days: 3,
    response_time_days: 1,
    internal_handoff_minutes: 0,
    external_safety_margin_days: 2,
    example: 'PO-1',
    require_qa: false,
    default_inspection_method_id: null,
    require_source_item_approval: false,
    assign_approved_material_to_item: false,
    overwrite_item_material_on_approval: false,
    external_first_step_needs_no_material: true,
    ...overrides,
  }
}

async function mountTab(permissions: string[], production: AdminProductionSettings) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  useAdminSettingsStore().settings = { production } as unknown as AllAdminSettings

  const wrapper = mountWithApp(AdminSettingsTabProduction, {
    pinia,
    attachTo: document.body,
  })
  await flushPromises()
  return wrapper
}

function firstStepToggle(wrapper: ReturnType<typeof mount>) {
  const label = i18n.global.t('adminSettings.production.externalFirstStepNeedsNoMaterial') as string
  const row = wrapper.findAll('.field-row--toggle').find((r) => r.find('label').text() === label)
  return row!.findComponent({ name: 'ToggleSwitch' })
}

function saveButton(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (i18n.global.t('common.save') as string))!
}

describe('AdminSettingsTabProduction external first step toggle', () => {
  beforeEach(() => {
    putMock.mockReset()
  })

  it('shows the stored value', async () => {
    const wrapper = await mountTab(
      ['write:settings'],
      makeProductionSettings({ external_first_step_needs_no_material: false }),
    )

    expect(firstStepToggle(wrapper).props('modelValue')).toBe(false)

    wrapper.unmount()
  })

  it('sends the toggled value on save', async () => {
    putMock.mockResolvedValue({
      data: makeProductionSettings({ external_first_step_needs_no_material: false }),
    })
    const wrapper = await mountTab(['write:settings'], makeProductionSettings())

    await firstStepToggle(wrapper).vm.$emit('update:modelValue', false)
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith(
      '/admin/settings/production',
      expect.objectContaining({ external_first_step_needs_no_material: false }),
    )

    wrapper.unmount()
  })

  it('is disabled without write:settings', async () => {
    const wrapper = await mountTab(['read:settings'], makeProductionSettings())

    expect(firstStepToggle(wrapper).props('disabled')).toBe(true)

    wrapper.unmount()
  })
})
