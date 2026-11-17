import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { TDocumentDefinitions } from 'pdfmake/interfaces'

import type { AppLocale } from '@/core/i18n'
import { usePublicBrandingStore } from '@/core/stores/publicBrandingStore'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { mountWithApp } from '@/test-utils/mountWithApp'
import type { DocumentPrinter, ReportExportFacts, ReportPrintOptions, ReportPrintTarget, UploadedPrintJobResponse } from '../api'
import type { ReportBranding, ReportOptionValues, ReportSpec } from '../types'

const api = vi.hoisted(() => ({
  getDocumentPrinters: vi.fn<() => Promise<DocumentPrinter[]>>(),
  printReport: vi.fn<
    (target: ReportPrintTarget, pdf: Blob, options: ReportPrintOptions, facts?: ReportExportFacts) => Promise<UploadedPrintJobResponse>
  >(),
  recordReportDownload: vi.fn<(target: ReportPrintTarget, facts: ReportExportFacts, pdf: Blob) => Promise<unknown>>(),
}))
const pdf = vi.hoisted(() => ({
  renderPdf: vi.fn<(definition: TDocumentDefinitions) => Promise<Blob>>(),
  downloadPdf: vi.fn<(blob: Blob, fileName: string) => void>(),
}))

const compose = vi.hoisted(() => ({
  composeReport: vi.fn<
    (spec: ReportSpec, branding: ReportBranding, locale: AppLocale, options: ReportOptionValues) => Promise<TDocumentDefinitions>
  >(),
}))

vi.mock('../api', () => api)
vi.mock('../utils/renderPdf', () => pdf)
vi.mock('../utils/composeReport', () => compose)

import ReportExportDialog from '../components/ReportExportDialog.vue'

const BLOB = new Blob(['%PDF-1.7'], { type: 'application/pdf' })
const TARGET: ReportPrintTarget = { document: 'calculation_report', rootPublicId: 'b0f6c5d4-0000-4000-8000-000000000001' }

function printer(overrides: Partial<DocumentPrinter> = {}): DocumentPrinter {
  return { id: 1, name: 'Office', location: null, transport: 'ipp', is_default: true, ...overrides }
}

function job(overrides: Partial<UploadedPrintJobResponse> = {}): UploadedPrintJobResponse {
  return {
    id: 5,
    public_id: 'b0f6c5d4-0000-4000-8000-000000000005',
    created: '2026-10-09T10:00:00Z',
    template_id: null,
    printer_id: 1,
    classifier: 'calculation_report',
    root_type: 'calculation',
    root_id: 17,
    copies: 1,
    status: 'sent',
    error_message: null,
    document_bytes: 8,
    trigger: 'manual',
    actor_id: 1,
    actor_full_name: 'Jane Doe',
    attributes_substituted: false,
    ...overrides,
  }
}

function spec(printTarget: ReportPrintTarget | null = TARGET): ReportSpec {
  return {
    title: 'Lift axis station 3',
    printTarget,
    build: () => ({ kind: 'Drive sizing', title: 'Lift axis station 3', details: [], body: [] }),
  }
}

/** The locale and options the dialog last exported with. */
function exported(): [AppLocale, ReportOptionValues] {
  const call = compose.composeReport.mock.calls.at(-1)
  if (!call) throw new Error('nothing exported')
  return [call[2], call[3]]
}

async function mountDialog(
  report: ReportSpec,
  permissions: string[] = ['print:documents'],
  slots: Record<string, string> = {},
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = { id: 1, permissions, is_systemuser: false } as never
  const wrapper = mountWithApp(ReportExportDialog, {
    pinia,
    props: { visible: false, report },
    slots,
    attachTo: document.body,
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

function byTestId(id: string): HTMLElement | null {
  return document.querySelector<HTMLElement>(`[data-testid="${id}"]`)
}

function button(id: string): HTMLButtonElement {
  const el = byTestId(id)
  if (!el) throw new Error(`missing ${id}`)
  return (el.tagName === 'BUTTON' ? el : el.querySelector('button')) as HTMLButtonElement
}

describe('ReportExportDialog', () => {
  beforeEach(() => {
    localStorage.clear()
    api.getDocumentPrinters.mockResolvedValue([printer(), printer({ id: 2, name: 'Workshop', is_default: false })])
    api.printReport.mockResolvedValue(job())
    api.recordReportDownload.mockResolvedValue({})
    pdf.renderPdf.mockResolvedValue(BLOB)
    compose.composeReport.mockResolvedValue({ content: [] })
  })

  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('downloads the report in the language picked in the dialog', async () => {
    const wrapper = await mountDialog(spec())

    const german = [...document.querySelectorAll('button')].find((el) => el.textContent?.includes('Deutsch'))
    german?.click()
    await flushPromises()
    button('report-download').click()
    await flushPromises()

    expect(exported()).toEqual(['deAT', {}])
    expect(pdf.downloadPdf).toHaveBeenCalledWith(BLOB, expect.stringMatching(/^Lift-axis-station-3_\d{4}-\d{2}-\d{2}\.pdf$/))
    expect(wrapper.emitted('update:visible')?.at(-1)).toEqual([false])
    wrapper.unmount()
  })

  it('records the download of a saved record in the export journal', async () => {
    const wrapper = await mountDialog({ ...spec(), engineVersion: 3 })

    button('report-download').click()
    await flushPromises()

    expect(api.recordReportDownload).toHaveBeenCalledWith(
      TARGET,
      { language: 'enGB', options: {}, reportVersion: __APP_VERSION__, engineVersion: 3 },
      BLOB,
    )
    wrapper.unmount()
  })

  it('journals nothing for unsaved inputs', async () => {
    const wrapper = await mountDialog(spec(null))

    button('report-download').click()
    await flushPromises()

    expect(pdf.downloadPdf).toHaveBeenCalled()
    expect(api.recordReportDownload).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('prints on the remembered printer, both sides', async () => {
    localStorage.setItem('glados.reportExport', JSON.stringify({ printerId: 2, twoSided: true }))
    const wrapper = await mountDialog(spec())

    button('report-print').click()
    await flushPromises()

    expect(exported()).toEqual(['enGB', {}])
    expect(api.printReport).toHaveBeenCalledWith(TARGET, BLOB, { printerId: 2, copies: 1, twoSided: true }, expect.objectContaining({ language: 'enGB' }))
    expect(wrapper.emitted('update:visible')?.at(-1)).toEqual([false])
    wrapper.unmount()
  })

  it('never asks a raw printer for two sides', async () => {
    localStorage.setItem('glados.reportExport', JSON.stringify({ printerId: 1, twoSided: true }))
    api.getDocumentPrinters.mockResolvedValue([printer({ transport: 'raw' })])
    const wrapper = await mountDialog(spec())

    expect(document.body.textContent).toContain('always prints on one side')
    button('report-print').click()
    await flushPromises()

    expect(api.printReport).toHaveBeenCalledWith(TARGET, BLOB, { printerId: 1, copies: 1, twoSided: false }, expect.objectContaining({ language: 'enGB' }))
    wrapper.unmount()
  })

  it('stays open when the printer rejects the job', async () => {
    api.printReport.mockResolvedValue(job({ status: 'failed', error_message: 'printer rejected the job' }))
    const wrapper = await mountDialog(spec())

    button('report-print').click()
    await flushPromises()

    expect(api.printReport).toHaveBeenCalledOnce()
    expect(wrapper.emitted('update:visible')?.at(-1)).not.toEqual([false])
    wrapper.unmount()
  })

  it('offers only the download for an unsaved record', async () => {
    const wrapper = await mountDialog(spec(null))

    expect(byTestId('report-print-unsaved')).not.toBeNull()
    expect(button('report-print').disabled).toBe(true)
    expect(api.getDocumentPrinters).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('offers the report options and remembers the last choice', async () => {
    const withOptions: ReportSpec = { ...spec(), options: [{ key: 'appendix', labelKey: 'reports.export.download' }] }
    const wrapper = await mountDialog(withOptions)

    const checkbox = document.querySelector<HTMLInputElement>('#report-option-appendix')!
    expect(checkbox.checked).toBe(false)
    checkbox.click()
    await flushPromises()
    button('report-download').click()
    await flushPromises()

    expect(exported()).toEqual(['enGB', { appendix: true }])
    expect(JSON.parse(localStorage.getItem('glados.reportExport') ?? '{}').options).toEqual({ appendix: true })
    wrapper.unmount()
  })

  it('exports with the company branding and the name of the user', async () => {
    const wrapper = await mountDialog(spec())
    useCurrentUserStore().user = { id: 1, full_name: 'Jane Doe', permissions: [], is_systemuser: false } as never

    button('report-download').click()
    await flushPromises()

    expect(compose.composeReport.mock.calls.at(-1)?.[1]).toEqual({
      appName: 'Glados',
      companyName: null,
      companyLogoUrl: null,
      domain: null,
      exportedBy: 'Jane Doe',
    })
    wrapper.unmount()
  })

  it('links the QR codes to the address the deployment is configured with', async () => {
    const wrapper = await mountDialog(spec())
    usePublicBrandingStore().branding = { app_name: 'Glados', domain: 'https://glados.example.com' } as never

    button('report-download').click()
    await flushPromises()

    expect(compose.composeReport.mock.calls.at(-1)?.[1]).toMatchObject({ domain: 'https://glados.example.com' })
    wrapper.unmount()
  })

  it('puts the handbook button a page passes in next to the title', async () => {
    const wrapper = await mountDialog(spec(), undefined, { handbook: '<button data-testid="help">?</button>' })

    const header = byTestId('report-export-header')
    expect(header?.textContent).toContain('Export report')
    expect(header?.querySelector('[data-testid="report-export-help"] [data-testid="help"]')).not.toBeNull()
    wrapper.unmount()
  })

  it('shows no help slot when the page passes none', async () => {
    const wrapper = await mountDialog(spec())

    expect(byTestId('report-export-header')?.textContent).toContain('Export report')
    expect(byTestId('report-export-help')).toBeNull()
    wrapper.unmount()
  })

  it('shows Print disabled with the missing permission and no printer section without the print permission', async () => {
    const wrapper = await mountDialog(spec(), [])

    expect(byTestId('report-print-section')).toBeNull()
    const print = button('report-print')
    expect(print.disabled).toBe(true)
    const span = print.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
    expect(span?.$_ptooltipValue).toBe('This needs the permission Print Documents.')
    expect(byTestId('report-download')).not.toBeNull()
    wrapper.unmount()
  })
})
