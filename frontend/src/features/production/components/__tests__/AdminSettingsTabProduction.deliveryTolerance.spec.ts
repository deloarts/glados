import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { userWithPermissions } from '@/test-utils/factories'
import { useAdminSettingsStore } from '@/features/admin-settings'

import type {
  AdminOrderSettings,
  AdminProductionSettings,
  AllAdminSettings,
} from '@/features/admin-settings'

// Mirrors the mount and store seeding of the tab's other specs. The
// delivery tolerances live on the order settings, which the tab reads and
// saves beside the production settings.

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

const production = {
  id: 1,
  public_id: '11111111-1111-1111-1111-111111111111',
  production_order_number_format: 'PO-{n}',
  default_weekly_hours: {},
  default_external_lead_days: 3,
  response_time_days: 1,
  example: 'PO-1',
  require_qa: false,
  default_inspection_method_id: null,
  require_source_item_approval: false,
  assign_approved_material_to_item: false,
  overwrite_item_material_on_approval: false,
} as AdminProductionSettings

const orders = {
  id: 1,
  over_delivery_tolerance_percent: 5,
  under_delivery_tolerance_percent: 2,
} as AdminOrderSettings

async function mountTab(settings: Partial<AllAdminSettings>) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(['write:settings'])
  useAdminSettingsStore().settings = settings as AllAdminSettings
  const wrapper = mountWithApp(AdminSettingsTabProduction, { pinia, attachTo: document.body })
  await flushPromises()
  return wrapper
}

function toleranceInput(wrapper: Awaited<ReturnType<typeof mountTab>>, labelKey: string) {
  const label = i18n.global.t(labelKey) as string
  const row = wrapper.findAll('.field-row').find((r) => r.find('label').text().startsWith(label))
  return row!.findComponent({ name: 'InputNumber' })
}

function saveButton(wrapper: Awaited<ReturnType<typeof mountTab>>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (i18n.global.t('common.save') as string))!
}

describe('AdminSettingsTabProduction delivery tolerances', () => {
  beforeEach(() => {
    putMock.mockReset()
    putMock.mockResolvedValue({ data: {} })
  })

  it('shows the tolerances of the order settings', async () => {
    const wrapper = await mountTab({ production, orders })

    const over = toleranceInput(wrapper, 'adminSettings.production.overDeliveryTolerance')
    const under = toleranceInput(wrapper, 'adminSettings.production.underDeliveryTolerance')
    expect(over.props('modelValue')).toBe(5)
    expect(under.props('modelValue')).toBe(2)

    wrapper.unmount()
  })

  it('saves the tolerances to the order settings', async () => {
    const wrapper = await mountTab({ production, orders })

    await toleranceInput(wrapper, 'adminSettings.production.overDeliveryTolerance').vm.$emit(
      'update:modelValue',
      10,
    )
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith('/admin/settings/orders', {
      over_delivery_tolerance_percent: 10,
      under_delivery_tolerance_percent: 2,
    })

    wrapper.unmount()
  })

  it('leaves the order settings alone when they were never read', async () => {
    const wrapper = await mountTab({ production })

    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledTimes(1)
    expect(putMock).toHaveBeenCalledWith('/admin/settings/production', expect.anything())

    wrapper.unmount()
  })
})
