import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import ConfirmationService from 'openvue/confirmationservice'


vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: [
        {
          id: 1,
          public_id: '11111111-1111-1111-1111-111111111111',
          created: '2026-01-01',
          changed: null,
          classifier: 'production_order_label',
          output_kind: 'zpl',
          root_type: 'production_order',
          trigger: 'production_order_completion_recorded',
          available_triggers: ['production_order_completion_recorded'],
          copies_rules: ['fixed', 'per_event_quantity'],
          source: '^XA^XZ',
          field_map: {},
          printer_id: null,
          printer_name: '',
          auto_print: false,
          copies_rule: 'fixed',
          copies_fixed: 1,
          max_copies: 50,
          design_dpi: 300,
          label_width_mm: 70,
          label_height_mm: 32,
          paper: null,
          enabled: true,
          note: null,
          creator_id: null,
          creator_full_name: '',
          changes: ['Seeded.'],
        },
        {
          id: 4,
          public_id: '44444444-4444-4444-4444-444444444444',
          created: '2026-01-01',
          changed: null,
          classifier: 'lot_label',
          output_kind: 'zpl',
          root_type: 'production_lot',
          trigger: 'lot_created',
          available_triggers: ['lot_created', 'lot_completed'],
          copies_rules: ['fixed', 'per_lot_quantity'],
          source: null,
          field_map: {},
          printer_id: null,
          printer_name: '',
          auto_print: false,
          copies_rule: 'fixed',
          copies_fixed: 1,
          max_copies: 50,
          design_dpi: null,
          label_width_mm: null,
          label_height_mm: null,
          paper: null,
          enabled: false,
          note: null,
          creator_id: null,
          creator_full_name: '',
          changes: ['Seeded.'],
        },
      ],
    }),
  },
}))

import PrintTemplateManagementTable from '../PrintTemplateManagementTable.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'

describe('PrintTemplateManagementTable with kind label', () => {
  it('mounts, loads templates, and renders classifier rows without errors', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountWithApp(PrintTemplateManagementTable, {
      props: { kind: 'label' },
      global: {
        plugins: [ConfirmationService],
      },
    })

    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])
    expect(wrapper.text()).toContain('Production Order Label')
    expect(wrapper.text()).toContain('Lot Label')

    wrapper.unmount()
  })
})
