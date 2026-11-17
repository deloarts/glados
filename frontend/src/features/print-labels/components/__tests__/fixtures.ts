import { useCurrentUserStore } from '@/core/stores/currentUserStore'

import type { UserResponse } from '@/core/types/userResponse'
import type { PrintTemplateResponse } from '../../types/printTemplateResponse'

export function makeLabelTemplate(
  overrides: Partial<PrintTemplateResponse> = {},
): PrintTemplateResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-01-01',
    changed: null,
    changed_by_id: null,
    changed_by_full_name: '',
    classifier: 'production_order_label',
    output_kind: 'zpl',
    root_type: 'production_order',
    trigger: 'production_order_completion_recorded',
    available_triggers: ['production_order_completion_recorded'],
    copies_rules: ['fixed', 'per_event_quantity'],
    source: '^XA^FD{order_number}^FS^XZ',
    field_map: { order_number: 'number' },
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
    ...overrides,
  }
}

export function makeDocketTemplate(
  overrides: Partial<PrintTemplateResponse> = {},
): PrintTemplateResponse {
  return makeLabelTemplate({
    id: 5,
    public_id: '55555555-5555-5555-5555-555555555555',
    classifier: 'lot_docket',
    output_kind: 'pdf_docket',
    root_type: 'production_lot',
    trigger: 'lot_created',
    available_triggers: ['lot_created', 'lot_completed'],
    copies_rules: ['fixed'],
    source: '{"blocks": [{"field": "lot_number"}]}',
    field_map: { lot_number: 'number' },
    design_dpi: null,
    label_width_mm: null,
    label_height_mm: null,
    paper: 'a4',
    ...overrides,
  })
}

/** Signs in a system user, who holds every permission. */
export function signInSystemUser(): void {
  useCurrentUserStore().user = {
    id: 999,
    permissions: [],
    is_systemuser: true,
  } as unknown as UserResponse
}
