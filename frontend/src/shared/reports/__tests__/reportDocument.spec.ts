import { describe, expect, it } from 'vitest'

import type { Content, DynamicContent } from 'pdfmake/interfaces'

import { reportTexts } from '@/test-utils/reportTexts'
import { reportDocument } from '../utils/reportDocument'
import type { ReportFrame } from '../utils/reportDocument'
import { reportFileName, reportTranslator } from '../utils/reportLocale'

function frame(overrides: Partial<ReportFrame> = {}): ReportFrame {
  return {
    locale: 'enGB',
    appName: 'Glados',
    companyName: 'Example Engineering GmbH',
    logo: null,
    kind: 'Drive sizing',
    exportedAt: 'Exported 9 Oct 2026, 14:05',
    title: 'Lift axis station 3',
    subtitle: 'Vertical axis, 140 kg, i = 12',
    details: [{ label: 'Status', value: 'Draft, not released' }],
    exportedBy: 'Exported by Jane Doe',
    identity: null,
    copyNotice: 'Printed copy, check the QR code for the current revision',
    pageLabel: (page, pages) => `Page ${page} of ${pages}`,
    ...overrides,
  }
}

function run(fn: DynamicContent | Content | undefined, page = 1, pages = 3): Content {
  return typeof fn === 'function' ? (fn(page, pages, { width: 595, height: 842, orientation: 'portrait' }) as Content) : (fn as Content)
}

describe('reportDocument', () => {
  it('frames the body with header, title block and footer', () => {
    const body: Content[] = [{ text: 'Body text' }]
    const definition = reportDocument(frame(), body)

    expect(definition.pageSize).toBe('A4')
    expect(definition.language).toBe('en-GB')
    expect(definition.info).toMatchObject({ title: 'Lift axis station 3', author: 'Example Engineering GmbH' })
    expect(reportTexts(run(definition.header))).toEqual(['Drive sizing', 'Exported 9 Oct 2026, 14:05'])
    expect(reportTexts(run(definition.footer, 2, 3))).toEqual([
      'Exported by Jane Doe',
      'Example Engineering GmbH',
      'Page 2 of 3',
    ])
    const content = reportTexts(definition.content)
    expect(content.slice(0, 2)).toEqual(['Lift axis station 3', 'Vertical axis, 140 kg, i = 12'])
    expect(content).toEqual(expect.arrayContaining(['Status', 'Draft, not released', 'Body text']))
  })

  it('puts the logo on the right of the header and a notice under the details', () => {
    const logo = 'data:image/png;base64,iVBORw0KGgo='
    const definition = reportDocument(frame({ logo, notice: { text: 'Results differ.', tone: 'warn' } }), [])

    const header = run(definition.header) as { stack: [{ columns: Array<{ stack?: Array<{ image?: string }> }> }] }
    const name = header.stack[0].columns.at(-1)?.stack?.[0]?.image ?? ''
    expect(definition.images?.[name]).toBe(logo)
    expect(reportTexts(definition.content)).toContain('Results differ.')
  })

  it('leaves the company out when none is configured', () => {
    const definition = reportDocument(frame({ companyName: null }), [])

    expect(reportTexts(run(definition.header))).toEqual(['Drive sizing', 'Exported 9 Oct 2026, 14:05'])
    expect(reportTexts(run(definition.footer))).not.toContain('Example Engineering GmbH')
    expect(definition.info?.author).toBeUndefined()
  })
})

describe('report identity', () => {
  it('puts a QR code of the record with its reference and the copy notice on every page', () => {
    const url = 'https://glados.example.com/resolve/0f6c1d2e'
    const definition = reportDocument(frame({ identity: { url, reference: 'Calculation 42' } }), [])

    for (const page of [1, 3]) {
      const footer = run(definition.footer, page, 3)
      expect(JSON.stringify(footer)).toContain(`"qr":"${url}"`)
      expect(reportTexts(footer)).toEqual(
        expect.arrayContaining(['Calculation 42', 'Printed copy, check the QR code for the current revision']),
      )
    }
  })

  it('has no QR code and no copy notice for a record that was never saved', () => {
    const footer = run(reportDocument(frame(), []).footer)

    expect(JSON.stringify(footer)).not.toContain('"qr"')
    expect(reportTexts(footer)).not.toContain('Printed copy, check the QR code for the current revision')
  })
})

describe('report locale', () => {
  it('translates into the report language, not the UI language', () => {
    expect(reportTranslator('deAT')('reports.document.page', { page: 1, pages: 2 })).toBe('Seite 1 von 2')
    expect(reportTranslator('enGB')('reports.document.page', { page: 1, pages: 2 })).toBe('Page 1 of 2')
  })

  it('builds a file name from the title and the date', () => {
    expect(reportFileName('Hubachse Ø25 / Station 3', new Date(2026, 9, 9))).toBe('Hubachse-25-Station-3_2026-10-09.pdf')
    expect(reportFileName('  ', new Date(2026, 0, 2))).toBe('report_2026-01-02.pdf')
  })
})
