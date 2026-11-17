import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PrintTemplateUpdateRequest } from '../../types/printTemplateRequest'
import type { PrintTemplateResponse } from '../../types/printTemplateResponse'

const getPrintTemplatesMock = vi.fn<() => Promise<PrintTemplateResponse[]>>()
const updatePrintTemplateMock =
  vi.fn<
    (classifier: string, payload: PrintTemplateUpdateRequest) => Promise<PrintTemplateResponse>
  >()
const resetPrintTemplateMock = vi.fn<(classifier: string) => Promise<PrintTemplateResponse>>()

vi.mock('../../api/getPrintTemplates', () => ({
  getPrintTemplates: () => getPrintTemplatesMock(),
}))
vi.mock('../../api/updatePrintTemplate', () => ({
  updatePrintTemplate: (classifier: string, payload: PrintTemplateUpdateRequest) =>
    updatePrintTemplateMock(classifier, payload),
}))
vi.mock('../../api/resetPrintTemplate', () => ({
  resetPrintTemplate: (classifier: string) => resetPrintTemplateMock(classifier),
}))

import { usePrintTemplatesStore } from '../printTemplatesStore'

// The store tests key rows by placeholder classifiers ('a', 'b') that are
// not real PrintClassifier values, so the builder accepts any string.
type TemplateOverrides = Partial<Omit<PrintTemplateResponse, 'classifier'>> & { classifier?: string }

function makeTemplate(overrides: TemplateOverrides = {}): PrintTemplateResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-01-01',
    changed: null,
    classifier: 'bought_item_label',
    output_kind: 'zpl',
    root_type: 'bought_item',
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
    max_copies: 10,
    design_dpi: 300,
    label_width_mm: 50,
    label_height_mm: 30,
    paper: null,
    enabled: true,
    note: null,
    creator_id: 1,
    creator_full_name: 'Creator',
    changes: [],
    ...overrides,
  } as PrintTemplateResponse
}

describe('usePrintTemplatesStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getPrintTemplatesMock.mockReset()
    updatePrintTemplateMock.mockReset()
    resetPrintTemplateMock.mockReset()
  })

  it('starts empty, not loading/mutating, with no filters and actions hidden', () => {
    const store = usePrintTemplatesStore()
    expect(store.loading).toBe(false)
    expect(store.mutating).toBe(false)
    expect(store.items).toEqual([])
    expect(store.search).toBe('')
    expect(store.showActions).toBe(false)
    expect(store.hasActiveFilters).toBe(false)
  })

  it('refresh populates items from getPrintTemplates', async () => {
    getPrintTemplatesMock.mockResolvedValue([makeTemplate()])
    const store = usePrintTemplatesStore()

    await store.refresh()

    expect(getPrintTemplatesMock).toHaveBeenCalled()
    expect(store.items).toEqual([makeTemplate()])
    expect(store.loading).toBe(false)
  })

  it('refresh surfaces a failed request through error, leaving items empty', async () => {
    getPrintTemplatesMock.mockRejectedValueOnce(new Error('network error'))
    const store = usePrintTemplatesStore()

    await store.refresh()

    expect(store.loading).toBe(false)
    expect(store.items).toEqual([])
  })

  it('triggerRefresh is aliased to refresh (no separate silent refresh)', async () => {
    getPrintTemplatesMock.mockResolvedValue([makeTemplate()])
    const store = usePrintTemplatesStore()

    await store.triggerRefresh()

    expect(getPrintTemplatesMock).toHaveBeenCalled()
    expect(store.items).toEqual([makeTemplate()])
  })

  it('labelTemplates/docketTemplates split items by output_kind', async () => {
    getPrintTemplatesMock.mockResolvedValue([
      makeTemplate({ id: 1, classifier: 'a', output_kind: 'zpl' }),
      makeTemplate({ id: 2, classifier: 'b', output_kind: 'pdf_docket' }),
    ])
    const store = usePrintTemplatesStore()
    await store.refresh()

    expect(store.labelTemplates.map((t) => t.id)).toEqual([1])
    expect(store.docketTemplates.map((t) => t.id)).toEqual([2])
  })

  it('update replaces the matching row in place and returns the updated template', async () => {
    getPrintTemplatesMock.mockResolvedValue([makeTemplate({ id: 1, classifier: 'a' })])
    const store = usePrintTemplatesStore()
    await store.refresh()
    const updated = makeTemplate({ id: 1, classifier: 'a', enabled: false })
    updatePrintTemplateMock.mockResolvedValue(updated)

    const result = await store.update('a', { enabled: false })

    expect(updatePrintTemplateMock).toHaveBeenCalledWith('a', { enabled: false })
    expect(result).toEqual(updated)
    expect(store.items[0]).toEqual(updated)
    expect(store.mutating).toBe(false)
  })

  it('update resets mutating and leaves items untouched when the request fails', async () => {
    getPrintTemplatesMock.mockResolvedValue([makeTemplate({ id: 1, classifier: 'a' })])
    const store = usePrintTemplatesStore()
    await store.refresh()
    updatePrintTemplateMock.mockRejectedValueOnce(new Error('422'))

    await expect(store.update('a', { enabled: false })).rejects.toThrow('422')

    expect(store.mutating).toBe(false)
    expect(store.items[0]).toEqual(makeTemplate({ id: 1, classifier: 'a' }))
  })

  it('reset replaces the matching row in place with the server-reset template', async () => {
    getPrintTemplatesMock.mockResolvedValue([makeTemplate({ id: 1, classifier: 'a', enabled: false })])
    const store = usePrintTemplatesStore()
    await store.refresh()
    const reset = makeTemplate({ id: 1, classifier: 'a', enabled: true })
    resetPrintTemplateMock.mockResolvedValue(reset)

    const result = await store.reset('a')

    expect(resetPrintTemplateMock).toHaveBeenCalledWith('a')
    expect(result).toEqual(reset)
    expect(store.items[0]).toEqual(reset)
    expect(store.mutating).toBe(false)
  })

  it('reset resets mutating and leaves items untouched when the request fails', async () => {
    getPrintTemplatesMock.mockResolvedValue([makeTemplate({ id: 1, classifier: 'a' })])
    const store = usePrintTemplatesStore()
    await store.refresh()
    resetPrintTemplateMock.mockRejectedValueOnce(new Error('500'))

    await expect(store.reset('a')).rejects.toThrow('500')

    expect(store.mutating).toBe(false)
    expect(store.items[0]).toEqual(makeTemplate({ id: 1, classifier: 'a' }))
  })

  it('toggleShowActions flips showActions', () => {
    const store = usePrintTemplatesStore()
    store.toggleShowActions()
    expect(store.showActions).toBe(true)
    store.toggleShowActions()
    expect(store.showActions).toBe(false)
  })

  it('hasActiveFilters reflects search, and clearAll resets it', () => {
    const store = usePrintTemplatesStore()
    store.search = 'zebra'
    expect(store.hasActiveFilters).toBe(true)

    store.clearAll()

    expect(store.search).toBe('')
    expect(store.hasActiveFilters).toBe(false)
  })
})
