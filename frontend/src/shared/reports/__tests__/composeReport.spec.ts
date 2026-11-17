import { describe, expect, it, vi } from 'vitest'
import type { Content, DynamicContent } from 'pdfmake/interfaces'

vi.mock('../utils/reportImage', () => ({
  loadCompanyLogo: vi.fn<(url: string | null) => Promise<string | null>>(async (url) =>
    url ? 'data:image/png;base64,iVBORw0KGgo=' : null,
  ),
}))

import { reportTexts } from '@/test-utils/reportTexts'
import type { ReportBranding, ReportContext, ReportSpec } from '../types'
import { composeReport, createReportContext, resolveUrl } from '../utils/composeReport'

const BRANDING: ReportBranding = {
  appName: 'Glados',
  companyName: 'Example Engineering GmbH',
  companyLogoUrl: '/api/v1/public/company/logo',
  domain: 'https://glados.example.com',
  exportedBy: 'Jane Doe',
}

function run(fn: DynamicContent | Content | undefined, page = 1, pages = 2): Content {
  return typeof fn === 'function' ? (fn(page, pages, { width: 595, height: 842, orientation: 'portrait' }) as Content) : (fn as Content)
}

function spec(build: ReportSpec['build']): ReportSpec {
  return { title: 'Press 12', printTarget: null, build }
}

describe('composeReport', () => {
  it('builds the content in the chosen language and puts it into the shared frame', async () => {
    let seen: ReportContext | null = null
    const definition = await composeReport(
      spec((context) => {
        seen = context
        return {
          kind: context.t('reports.export.title'),
          title: 'Press 12',
          subtitle: 'Hydraulics',
          details: [{ label: 'Status', value: 'Draft' }],
          body: [{ text: 'Body' }],
        }
      }),
      BRANDING,
      'deAT',
      { hints: true },
    )

    expect(seen!.locale).toBe('deAT')
    expect(seen!.options).toEqual({ hints: true })
    const header = reportTexts(run(definition.header))
    expect(header[0]).toBe('Bericht exportieren')
    expect(header[1]).toMatch(/^Exportiert am /)
    expect(reportTexts(run(definition.footer, 2, 3))).toEqual(
      expect.arrayContaining(['Example Engineering GmbH', 'Seite 2 von 3']),
    )
    expect(reportTexts(run(definition.footer))).toContain('Exportiert von Jane Doe')
    expect(reportTexts(definition.content)).toEqual(expect.arrayContaining(['Press 12', 'Hydraulics', 'Status', 'Body']))
    expect(definition.images).toEqual({ companyLogo: 'data:image/png;base64,iVBORw0KGgo=' })
  })

  it('writes every report as an archival PDF with its metadata', async () => {
    const definition = await composeReport(
      spec(() => ({ kind: 'Checklist', title: 'Press 12', details: [], body: [] })),
      BRANDING,
      'enGB',
      {},
    )

    expect(definition.subset).toBe('PDF/A-2b')
    expect(definition.version).toBe('1.7')
    expect(definition.displayTitle).toBe(true)
    expect(definition.language).toBe('en-GB')
    expect(definition.info).toMatchObject({
      title: 'Press 12',
      subject: 'Checklist',
      author: 'Example Engineering GmbH',
      creator: 'Glados',
    })
  })

  it('leaves out a subtitle that only repeats the title', async () => {
    const definition = await composeReport(
      spec(() => ({ kind: 'Drive sizing', title: 'Vertical axis', subtitle: 'Vertical axis', details: [], body: [] })),
      BRANDING,
      'enGB',
      {},
    )

    expect(reportTexts(definition.content).filter((text) => text === 'Vertical axis')).toHaveLength(1)
  })
})

describe('report identity', () => {
  it('points the QR code to the resolve page of the configured domain', async () => {
    const definition = await composeReport(
      spec(() => ({
        kind: 'Checklist',
        title: 'Press 12',
        details: [],
        identity: { publicId: '0f6c1d2e', reference: 'Checklist 7, revision B' },
        body: [],
      })),
      BRANDING,
      'enGB',
      {},
    )

    const footer = run(definition.footer)
    expect(JSON.stringify(footer)).toContain('"qr":"https://glados.example.com/resolve/0f6c1d2e"')
    expect(reportTexts(footer)).toContain('Checklist 7, revision B')
  })

  it('falls back to the address the app runs at', () => {
    expect(resolveUrl('abc', null)).toBe(`${window.location.origin}/resolve/abc`)
    expect(resolveUrl('abc', 'https://glados.example.com/')).toBe('https://glados.example.com/resolve/abc')
  })
})

describe('createReportContext', () => {
  it('formats dates in the fixed format of the language', () => {
    const context = createReportContext('deAT')

    expect(context.date('2026-10-09')).toBe('09.10.2026')
    expect(context.date('')).toBe('')
    expect(context.t('reports.document.page', { page: 1, pages: 1 })).toBe('Seite 1 von 1')
  })
})
