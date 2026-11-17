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
          id: 5,
          public_id: '55555555-5555-5555-5555-555555555555',
          created: '2026-01-01',
          changed: null,
          classifier: 'lot_docket',
          output_kind: 'pdf_docket',
          root_type: 'production_lot',
          trigger: 'lot_created',
          available_triggers: ['lot_created', 'lot_completed'],
          copies_rules: ['fixed'],
          source: '{"page": {"width_mm": 148, "height_mm": 210}, "blocks": []}',
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
          paper: 'a4',
          enabled: true,
          note: null,
          creator_id: null,
          creator_full_name: '',
          changes: ['Seeded.'],
        },
        {
          id: 6,
          public_id: '66666666-6666-6666-6666-666666666666',
          created: '2026-01-01',
          changed: null,
          classifier: 'made_item_docket',
          output_kind: 'pdf_docket',
          root_type: 'made_item',
          trigger: null,
          available_triggers: [],
          copies_rules: ['fixed'],
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
          paper: 'a4',
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

describe('PrintTemplateManagementTable with kind docket', () => {
  it('mounts, loads templates, and renders only docket rows without errors', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountWithApp(PrintTemplateManagementTable, {
      props: { kind: 'docket' },
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

    // Docket rows render...
    expect(wrapper.text()).toContain('Lot Docket')
    expect(wrapper.text()).toContain('Made Item Docket')
    // ...the ZPL-only row does not (output_kind filtering works).
    expect(wrapper.text()).not.toContain('Production Order Label')
    // The docket-only Page Size column renders a translated label for the
    // raw "a4" paper value.
    expect(wrapper.text()).toContain('A4')

    wrapper.unmount()
  })
})
