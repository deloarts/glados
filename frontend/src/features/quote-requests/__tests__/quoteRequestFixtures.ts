import type {
  QuoteRequestLineResponse,
  QuoteRequestResponse,
  QuoteRequestSupplierResponse,
  QuoteResponse,
} from '../types/quoteRequestsResponse'

export function makeQuote(overrides: Partial<QuoteResponse> = {}): QuoteResponse {
  return {
    line_id: 1,
    unit_price: null,
    no_offer: false,
    lead_time_days: null,
    min_quantity: null,
    note: null,
    substitute_bought_item_id: null,
    substitute_source_item_id: null,
    substitute_reason: null,
    substitute_item_name: '',
    substitute_item_code: '',
    ...overrides,
  }
}

export function makeLine(overrides: Partial<QuoteRequestLineResponse> = {}): QuoteRequestLineResponse {
  return {
    id: 1,
    public_id: 'aaaaaaaa-0000-0000-0000-000000000001',
    position: 1,
    line_type: 'BOUGHT',
    quantity: 4,
    unit: 'PCS',
    created: '2026-10-29T08:00:00Z',
    note: null,
    item_name: 'Screw M6',
    item_code: 'M6-20',
    bought_item_id: 5,
    source_item_id: null,
    lot_position_id: null,
    lot_id: null,
    lot_number: '',
    virtual_name: null,
    project_id: 3,
    project_number: 'P-1',
    state: 'open',
    awarded_supplier_id: null,
    awarded_price: null,
    awarded_at: null,
    award_voided: false,
    dropped_at: null,
    order_item_id: null,
    order_id: null,
    order_number: '',
    substitute_reason: null,
    substituted_by_line_id: null,
    demands: [],
    cheapest_supplier_id: null,
    ...overrides,
  }
}

export function makeRow(
  overrides: Partial<QuoteRequestSupplierResponse> = {},
): QuoteRequestSupplierResponse {
  return {
    id: 11,
    public_id: 'bbbbbbbb-0000-0000-0000-000000000011',
    supplier_id: 21,
    supplier_name: 'Acme',
    supplier_archived: false,
    position: 1,
    sent_at: null,
    responded_at: null,
    declined_at: null,
    valid_until: null,
    note: null,
    quotes: [],
    extra_costs: [],
    lines_total: 0,
    extra_costs_total: 0,
    total: 0,
    priced_lines: 0,
    not_asked_line_ids: [],
    has_awarded_lines: false,
    ...overrides,
  }
}

export function makeRequest(overrides: Partial<QuoteRequestResponse> = {}): QuoteRequestResponse {
  return {
    id: 7,
    public_id: 'cccccccc-0000-0000-0000-000000000007',
    request_number: 'RFQ-26-00007',
    status: 'sent',
    actions: ['send', 'award', 'cancel'],
    created: '2026-10-29T08:00:00Z',
    changed: null,
    note: null,
    deadline: null,
    closed_at: null,
    canceled_at: null,
    edit_version: 2,
    creator_id: 1,
    creator: null,
    changed_by_id: null,
    changed_by: null,
    lines: [makeLine()],
    suppliers: [makeRow()],
    cheapest_complete_supplier_id: null,
    ...overrides,
  }
}
